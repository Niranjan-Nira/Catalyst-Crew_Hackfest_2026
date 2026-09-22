#!/usr/bin/env python3
"""
build_sqlite.py — Turn the encyclopedia into a queryable SQLite database.

Schema is designed around the three questions an AI agent (or a human) asks
when handed a symptom: "what is this" (entries + events), "why does it happen"
(root_causes), and "what do I do" (diagnostic_steps + resolutions). A parallel
FTS5 virtual table gives keyword search without any embedding model, so this
file alone is a working RAG backend for exact/fuzzy matches (e.g. "event 7000",
"0xC0000005", "port exhaustion") — pair it with build_vectorstore.py for
semantic/paraphrase matching on top.

Usage:
    python3 build_sqlite.py /path/to/win-encyclopedia --out encyclopedia.db

Then query it directly:
    sqlite3 encyclopedia.db "SELECT entry_id, title FROM entries_fts WHERE entries_fts MATCH 'port exhaustion';"
"""
import argparse
import re
import sqlite3
from pathlib import Path

from parse_entries import parse_corpus

SCHEMA = """
CREATE TABLE entries (
    entry_id            TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    category            TEXT,
    severity_for_triage TEXT,
    event_id            TEXT,       -- numeric/string Windows event ID, if category=event-id
    event_provider      TEXT,
    event_channel       TEXT,
    event_level         TEXT,
    applies_to          TEXT,       -- comma-joined
    status              TEXT,
    curator             TEXT,
    last_reviewed       TEXT,
    overview            TEXT,
    meaning             TEXT,
    impact              TEXT,
    full_text           TEXT,       -- entire entry body, for FTS and for feeding an LLM verbatim
    source_file         TEXT
);

-- One row per root cause, preserving stated prevalence and order (rank).
-- This is the table an anomaly-matching agent joins into for "why".
CREATE TABLE root_causes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    TEXT NOT NULL REFERENCES entries(entry_id),
    rank        INTEGER,            -- order as listed (1 = most common per the entry)
    prevalence  TEXT,               -- 'very common' | 'common' | 'uncommon' | 'rare' | NULL if unstated
    cause_text  TEXT NOT NULL
);

-- One row per numbered/bulleted diagnostic step, in order, with the exact
-- command extracted separately so a tool-calling agent can execute it.
CREATE TABLE diagnostic_steps (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id     TEXT NOT NULL REFERENCES entries(entry_id),
    step_order   INTEGER,
    step_text    TEXT NOT NULL,
    command      TEXT,              -- extracted fenced-code-block content, if present
    command_lang TEXT,               -- powershell | cmd | text | ...
    modifies_system INTEGER DEFAULT 0  -- 1 if step is flagged [MODIFIES SYSTEM]
);

CREATE TABLE resolutions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    TEXT NOT NULL REFERENCES entries(entry_id),
    resolution_text TEXT NOT NULL
);

CREATE TABLE related_entries (
    entry_id         TEXT NOT NULL REFERENCES entries(entry_id),
    related_entry_id TEXT NOT NULL,
    PRIMARY KEY (entry_id, related_entry_id)
);

CREATE TABLE sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    TEXT NOT NULL REFERENCES entries(entry_id),
    repo        TEXT,
    license     TEXT
);

-- Full text search over title + full entry body. This is what a keyword-based
-- RAG retriever queries first. Standalone (non-contentless) FTS5 table so
-- entry_id/title come back directly from the FTS query itself.
CREATE VIRTUAL TABLE entries_fts USING fts5(
    entry_id,
    title,
    full_text
);

CREATE INDEX idx_entries_category ON entries(category);
CREATE INDEX idx_entries_severity ON entries(severity_for_triage);
CREATE INDEX idx_entries_event_id ON entries(event_id);
CREATE INDEX idx_root_causes_entry ON root_causes(entry_id);
CREATE INDEX idx_diag_steps_entry ON diagnostic_steps(entry_id);
"""

CAUSE_LINE_RE = re.compile(
    r"^\d+\.\s+\*\*(.+?)\*\*\s*—?\s*(.*?)(?:\*(very common|common|uncommon|rare)\*)?\.?\s*$",
    re.MULTILINE,
)
STEP_RE = re.compile(r"^(\d+)\.\s+(.+?)(?=\n\d+\.|\Z)", re.DOTALL | re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
MODIFIES_RE = re.compile(r"\[MODIFIES SYSTEM\]")


def extract_root_causes(section_text):
    """Parse the 'Likely Root Causes' section's numbered list into structured rows."""
    if not section_text:
        return []
    rows = []
    # Split on top-level numbered items (lines starting "N. ")
    items = re.split(r"\n(?=\d+\.\s)", section_text.strip())
    for i, item in enumerate(items, start=1):
        item = item.strip()
        if not item or not re.match(r"^\d+\.", item):
            continue
        text = re.sub(r"^\d+\.\s*", "", item)
        prevalence = None
        m = re.search(r"\*(very common|common|uncommon|rare)[^*]*\*", text, re.IGNORECASE)
        if m:
            prevalence = m.group(1).lower()
        rows.append({"rank": i, "prevalence": prevalence, "cause_text": text.strip()})
    return rows


def extract_diagnostic_steps(section_text):
    """Parse the 'Diagnostic Procedure' section into ordered steps with any
    embedded command extracted separately."""
    if not section_text:
        return []
    steps = []
    items = re.split(r"\n(?=\d+\.\s)", section_text.strip())
    order = 0
    for item in items:
        item = item.strip()
        if not item or not re.match(r"^\d+\.", item):
            continue
        order += 1
        text = re.sub(r"^\d+\.\s*", "", item)
        modifies = bool(MODIFIES_RE.search(text))
        code_match = CODE_BLOCK_RE.search(text)
        command, lang = None, None
        if code_match:
            lang = code_match.group(1) or None
            command = code_match.group(2).strip()
        # strip the code block from the descriptive text, keep it readable
        clean_text = CODE_BLOCK_RE.sub("", text).strip()
        steps.append({
            "step_order": order,
            "step_text": clean_text,
            "command": command,
            "command_lang": lang,
            "modifies_system": 1 if modifies else 0,
        })
    return steps


def extract_resolutions(section_text):
    if not section_text:
        return []
    # Resolution sections are prose, sometimes with a "Keyed to causes:" list.
    # Store as one row per sentence-like clause split on '; ' to keep granularity
    # usable for join-based lookup, falling back to the whole block.
    parts = [p.strip() for p in re.split(r"(?<=[.;])\s+(?=[A-Z(])", section_text.strip()) if p.strip()]
    return parts or [section_text.strip()]


def build(root: Path, out_path: Path):
    entries = parse_corpus(root)

    if out_path.exists():
        out_path.unlink()
    conn = sqlite3.connect(out_path)
    conn.executescript(SCHEMA)

    for e in entries:
        event = e.get("event") or {}
        applies_to = e.get("applies_to") or []
        if isinstance(applies_to, list):
            applies_to = ", ".join(applies_to)

        sections = e.get("sections", {})
        overview = sections.get("Overview", "")
        meaning = sections.get("Meaning") or next(
            (v for k, v in sections.items() if k.startswith("Meaning")), ""
        )
        # Some entries fold "meaning" into Overview and omit a separate
        # section (valid per the style guide when Overview already states
        # the interpretation) — fall back so consumers always get a summary.
        if not meaning:
            meaning = overview
        impact = sections.get("Impact", "")

        conn.execute(
            """INSERT INTO entries
               (entry_id, title, category, severity_for_triage, event_id,
                event_provider, event_channel, event_level, applies_to,
                status, curator, last_reviewed, overview, meaning, impact,
                full_text, source_file)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                e["entry_id"], e.get("title"), e.get("category"),
                e.get("severity_for_triage"),
                str(event.get("id")) if event.get("id") is not None else None,
                event.get("provider"), event.get("channel"), event.get("level"),
                applies_to, e.get("status"), e.get("curator"),
                str(e.get("last_reviewed")), overview, meaning, impact,
                e.get("full_text", ""), e.get("source_file"),
            ),
        )

        rc_section = sections.get("Likely Root Causes", "")
        for rc in extract_root_causes(rc_section):
            conn.execute(
                "INSERT INTO root_causes (entry_id, rank, prevalence, cause_text) VALUES (?,?,?,?)",
                (e["entry_id"], rc["rank"], rc["prevalence"], rc["cause_text"]),
            )

        diag_section = sections.get("Diagnostic Procedure", "")
        for st in extract_diagnostic_steps(diag_section):
            conn.execute(
                """INSERT INTO diagnostic_steps
                   (entry_id, step_order, step_text, command, command_lang, modifies_system)
                   VALUES (?,?,?,?,?,?)""",
                (e["entry_id"], st["step_order"], st["step_text"],
                 st["command"], st["command_lang"], st["modifies_system"]),
            )

        res_section = sections.get("Resolution", "")
        for res_text in extract_resolutions(res_section):
            conn.execute(
                "INSERT INTO resolutions (entry_id, resolution_text) VALUES (?,?)",
                (e["entry_id"], res_text),
            )

        for rel_id in e.get("related_entry_ids", []):
            if rel_id != e["entry_id"]:
                conn.execute(
                    "INSERT OR IGNORE INTO related_entries (entry_id, related_entry_id) VALUES (?,?)",
                    (e["entry_id"], rel_id),
                )

        for src in (e.get("sources") or []):
            if isinstance(src, dict):
                conn.execute(
                    "INSERT INTO sources (entry_id, repo, license) VALUES (?,?,?)",
                    (e["entry_id"], src.get("repo"), src.get("license")),
                )

        conn.execute(
            "INSERT INTO entries_fts (entry_id, title, full_text) VALUES (?,?,?)",
            (e["entry_id"], e.get("title", ""), e.get("full_text", "")),
        )

    conn.commit()

    counts = {}
    for table in ["entries", "root_causes", "diagnostic_steps", "resolutions", "related_entries", "sources"]:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Path to the win-encyclopedia directory")
    ap.add_argument("--out", default="encyclopedia.db", help="Output SQLite file")
    args = ap.parse_args()

    counts = build(Path(args.root), Path(args.out))
    print(f"Built {args.out}")
    for table, n in counts.items():
        print(f"  {table}: {n} rows")


if __name__ == "__main__":
    main()
