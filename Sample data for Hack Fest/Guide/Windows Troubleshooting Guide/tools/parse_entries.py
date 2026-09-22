#!/usr/bin/env python3
"""
parse_entries.py — Parse the encyclopedia's markdown chapter files into
structured records: one dict per entry, with front matter fields and each
named section's text broken out separately.

This is the shared parsing layer used by both build_sqlite.py and
build_vectorstore.py — run it standalone to sanity-check extraction:

    python3 parse_entries.py /path/to/win-encyclopedia --json out.json

No third-party dependencies (stdlib only: re, yaml-lite via manual parsing to
avoid requiring PyYAML — but PyYAML is used if present, falling back to a
minimal parser for the flat key:value / list front matter this corpus uses).
"""
import argparse
import json
import re
from pathlib import Path

SECTION_NAMES = [
    "Overview", "Historical / Technical Context", "Historical Context",
    "Message Text & Fields", "Meaning", "Likely Root Causes",
    "Diagnostic Procedure", "Resolution", "Key Figures & Ecosystem",
    "Impact", "Related Entries", "References & Attribution",
]

ENTRY_SPLIT_RE = re.compile(r"\n---\n(?=entry_id:)")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
SECTION_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
ENTRY_ID_RE = re.compile(r"\bV(\d+)\.C(\d+)\.E([\w]+)\b")


def _try_yaml(text):
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except Exception:
        return None


def _minimal_frontmatter_parse(text):
    """Fallback parser for the flat frontmatter shape used in this corpus:
    scalar: value
    list_key: [a, b, c]
    nested blocks like `event: { id: 7, provider: "x", channel: System }`
    """
    data = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\w[\w_]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            items = [i.strip().strip('"').strip("'") for i in inner.split(",") if i.strip()]
            data[key] = items
        elif val.startswith("{") and val.endswith("}"):
            inner = val[1:-1]
            sub = {}
            for pair in re.findall(r'(\w+):\s*("[^"]*"|[^,}]+)', inner):
                k, v = pair
                sub[k] = v.strip().strip('"')
            data[key] = sub
        else:
            data[key] = val.strip('"').strip("'")
    return data


def parse_frontmatter(raw):
    parsed = _try_yaml(raw)
    if isinstance(parsed, dict):
        return parsed
    return _minimal_frontmatter_parse(raw)


def split_sections(body):
    """Split an entry body into {section_name: text} using '## ' headers."""
    sections = {}
    headers = list(SECTION_HEADER_RE.finditer(body))
    for i, h in enumerate(headers):
        name = h.group(1).strip()
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def extract_related_ids(text):
    return sorted(set(f"V{m.group(1)}.C{m.group(2)}.E{m.group(3)}" for m in ENTRY_ID_RE.finditer(text)))


def parse_chapter_file(path: Path):
    raw = path.read_text(encoding="utf-8")
    # The file may open with a title/H1 + prose before the first entry block;
    # split on the boundary before each `entry_id:` frontmatter.
    chunks = re.split(r"\n---\nentry_id:", raw)
    entries = []
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            continue  # preamble/title text before the first entry
        chunk = "entry_id:" + chunk
        m = FRONTMATTER_RE.match("---\n" + chunk)
        if not m:
            # last entry in file has no trailing '---' before EOF in this shape;
            # handle by locating the second '---' manually
            first_dash = chunk.find("\n---\n")
            if first_dash == -1:
                continue
            fm_text = chunk[:first_dash]
            body = chunk[first_dash + 5:]
        else:
            fm_text, body = m.group(1), m.group(2)
            fm_text = fm_text[len("entry_id:"):]
            fm_text = "entry_id:" + fm_text
        fm = parse_frontmatter(fm_text)
        sections = split_sections(body)
        related_raw = sections.get("Related Entries", "")
        record = {
            "entry_id": fm.get("entry_id"),
            "title": fm.get("title"),
            "category": fm.get("category"),
            "event": fm.get("event"),
            "severity_for_triage": fm.get("severity_for_triage"),
            "applies_to": fm.get("applies_to"),
            "sources": fm.get("sources"),
            "last_reviewed": fm.get("last_reviewed"),
            "curator": fm.get("curator"),
            "status": fm.get("status"),
            "source_file": str(path),
            "sections": sections,
            "related_entry_ids": extract_related_ids(related_raw),
            "full_text": body.strip(),
        }
        if record["entry_id"]:
            entries.append(record)
    return entries


def parse_corpus(root: Path):
    all_entries = []
    for md_path in sorted(root.glob("vol-*/**/*.md")):
        try:
            all_entries.extend(parse_chapter_file(md_path))
        except Exception as e:
            print(f"WARN: failed to parse {md_path}: {e}")
    return all_entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Path to the win-encyclopedia directory")
    ap.add_argument("--json", help="Write parsed entries to this JSON file")
    args = ap.parse_args()

    root = Path(args.root)
    entries = parse_corpus(root)
    print(f"Parsed {len(entries)} entries from {root}")
    by_cat = {}
    for e in entries:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
    for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat or '(none)'}: {n}")

    if args.json:
        Path(args.json).write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {args.json}")


if __name__ == "__main__":
    main()
