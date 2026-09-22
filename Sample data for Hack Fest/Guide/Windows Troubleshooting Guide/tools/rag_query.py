#!/usr/bin/env python3
"""
rag_query.py — The retrieval half of a RAG pipeline for this encyclopedia:
given a raw symptom (a log line, an event ID, a free-text description of an
anomaly), return the most relevant entries with their structured root causes,
diagnostic steps, and resolutions assembled into a single context block ready
to hand to an LLM for the final "here's what's likely wrong and what to do"
answer.

Retrieval strategy — hybrid, in this order:
  1. Exact event-ID match (fast path): if the query contains something that
     looks like a Windows event ID or a hex error code, look it up directly
     in `entries` / `entries.event_id` first. This is the highest-precision
     signal available and should always win when present.
  2. FTS5 keyword search (works out of the box, no embedding model needed).
  3. Vector similarity search (optional — only runs if a Chroma store is
     found at --vecstore; this is what catches paraphrased symptoms that
     share no vocabulary with the corpus).
Results from all fired strategies are merged and de-duplicated, keeping the
best (first) rank for each entry_id.

This script does NOT call an LLM itself — it prepares the retrieval context.
See the `--llm-prompt` flag to print a ready-to-send prompt template, or
import `answer_context()` from your own agent/orchestration code.

Usage:
    # Fast path / keyword only (works immediately after build_sqlite.py):
    python3 rag_query.py encyclopedia.db "service failed to start access denied"
    python3 rag_query.py encyclopedia.db "event 7000"
    python3 rag_query.py encyclopedia.db "0xC0000005"

    # With semantic search too (after build_vectorstore.py --backend chroma):
    python3 rag_query.py encyclopedia.db "computer keeps restarting for no reason" \
        --vecstore ./chroma_store

    # Emit an LLM-ready prompt instead of raw JSON:
    python3 rag_query.py encyclopedia.db "server won't start, error 1053" --llm-prompt
"""
import argparse
import json
import re
import sqlite3

EVENT_ID_RE = re.compile(r"\bevent\s*(?:id\s*)?[:#]?\s*(\d{1,6})\b", re.IGNORECASE)
HEX_CODE_RE = re.compile(r"\b0x[0-9A-Fa-f]{6,8}\b")
BARE_ID_RE = re.compile(r"\b(\d{2,6})\b")


def find_exact_matches(conn, query):
    """Fast path: pull out anything that looks like an event ID or hex error
    code and look it up directly."""
    hits = []
    for m in HEX_CODE_RE.finditer(query):
        code = m.group(0)
        rows = conn.execute(
            "SELECT entry_id, title FROM entries_fts WHERE entries_fts MATCH ? LIMIT 5",
            (json.dumps(code),),  # phrase match, FTS5 quoting via json.dumps is a simple safe quoter
        ).fetchall()
        hits.extend(rows)

    m = EVENT_ID_RE.search(query)
    if m:
        eid = m.group(1)
        rows = conn.execute(
            "SELECT entry_id, title FROM entries WHERE event_id = ?", (eid,)
        ).fetchall()
        hits.extend(rows)

    return [{"entry_id": r[0], "title": r[1], "match_type": "exact"} for r in hits]


def fts_search(conn, query, limit=8):
    # Build a permissive OR query from the significant words so partial
    # phrasing still matches (FTS5 default MATCH is AND-ish across terms
    # for the bareword form; OR-join gives broader recall for a first pass).
    words = re.findall(r"[A-Za-z0-9_]+", query)
    stop = {"the", "a", "an", "is", "was", "on", "to", "of", "for", "and", "in",
            "my", "it", "with", "not", "keeps", "keep"}
    terms = [w for w in words if w.lower() not in stop and len(w) > 2]
    if not terms:
        return []
    match_expr = " OR ".join(terms)
    rows = conn.execute(
        """SELECT entry_id, title, bm25(entries_fts) as score
           FROM entries_fts WHERE entries_fts MATCH ?
           ORDER BY score LIMIT ?""",
        (match_expr, limit),
    ).fetchall()
    return [{"entry_id": r[0], "title": r[1], "match_type": "fts", "score": r[2]} for r in rows]


def vector_search(vecstore_path, query, limit=5):
    """Optional semantic pass. Requires chromadb + sentence-transformers and
    a store built by build_vectorstore.py --backend chroma. Returns []
    silently if the dependency or store isn't available, so this script
    still works standalone with just SQLite."""
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return []
    try:
        client = chromadb.PersistentClient(path=vecstore_path)
        coll = client.get_collection("windows_troubleshooting_encyclopedia")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        qvec = model.encode([query], normalize_embeddings=True).tolist()
        res = coll.query(query_embeddings=qvec, n_results=limit)
        out = []
        for eid, meta, dist in zip(res["ids"][0], res["metadatas"][0], res["distances"][0]):
            out.append({"entry_id": eid, "title": meta.get("title", ""),
                        "match_type": "vector", "score": dist})
        return out
    except Exception as e:
        print(f"[vector_search skipped: {e}]")
        return []


def fetch_full_record(conn, entry_id):
    row = conn.execute(
        """SELECT entry_id, title, category, severity_for_triage, event_id,
                  event_provider, overview, meaning, impact, status
           FROM entries WHERE entry_id = ?""",
        (entry_id,),
    ).fetchone()
    if not row:
        return None
    record = {
        "entry_id": row[0], "title": row[1], "category": row[2],
        "severity_for_triage": row[3], "event_id": row[4], "event_provider": row[5],
        "overview": row[6], "meaning": row[7], "impact": row[8], "status": row[9],
    }
    record["root_causes"] = [
        {"rank": r[0], "prevalence": r[1], "text": r[2]}
        for r in conn.execute(
            "SELECT rank, prevalence, cause_text FROM root_causes WHERE entry_id=? ORDER BY rank",
            (entry_id,),
        ).fetchall()
    ]
    record["diagnostic_steps"] = [
        {"order": r[0], "text": r[1], "command": r[2], "command_lang": r[3], "modifies_system": bool(r[4])}
        for r in conn.execute(
            """SELECT step_order, step_text, command, command_lang, modifies_system
               FROM diagnostic_steps WHERE entry_id=? ORDER BY step_order""",
            (entry_id,),
        ).fetchall()
    ]
    record["resolutions"] = [
        r[0] for r in conn.execute(
            "SELECT resolution_text FROM resolutions WHERE entry_id=?", (entry_id,)
        ).fetchall()
    ]
    record["related_entries"] = [
        r[0] for r in conn.execute(
            "SELECT related_entry_id FROM related_entries WHERE entry_id=?", (entry_id,)
        ).fetchall()
    ]
    return record


def retrieve(db_path, query, vecstore_path=None, top_k=5):
    conn = sqlite3.connect(db_path)

    merged = {}
    for hit in find_exact_matches(conn, query):
        merged.setdefault(hit["entry_id"], hit)
    for hit in fts_search(conn, query, limit=top_k * 2):
        merged.setdefault(hit["entry_id"], hit)
    if vecstore_path:
        for hit in vector_search(vecstore_path, query, limit=top_k):
            merged.setdefault(hit["entry_id"], hit)

    ordered_ids = list(merged.keys())[:top_k]
    results = [fetch_full_record(conn, eid) for eid in ordered_ids]
    conn.close()
    return [r for r in results if r]


def build_llm_prompt(query, results):
    """A ready-to-send prompt: the retrieved entries as grounding context,
    with an explicit instruction structure for anomaly / root cause /
    recommendation output. Swap this template for your own system prompt as
    needed — the point is the CONTEXT block, which is the actual RAG payload."""
    context_blocks = []
    for r in results:
        causes = "\n".join(f"  - ({c['prevalence'] or 'n/a'}) {c['text']}" for c in r["root_causes"]) or "  (none listed)"
        steps = "\n".join(f"  {s['order']}. {s['text']}" + (f"\n     command: {s['command']}" if s['command'] else "")
                           for s in r["diagnostic_steps"]) or "  (none listed)"
        resolutions = "\n".join(f"  - {x}" for x in r["resolutions"]) or "  (see diagnostic steps)"
        context_blocks.append(f"""
### {r['entry_id']} — {r['title']}  [severity: {r['severity_for_triage']}, status: {r['status']}]
Overview: {r['overview']}
Meaning: {r['meaning']}
Likely Root Causes:
{causes}
Diagnostic Steps:
{steps}
Resolution:
{resolutions}
Impact: {r['impact']}
Related: {', '.join(r['related_entries']) or 'none'}
""".strip())

    context = "\n\n".join(context_blocks)
    prompt = f"""You are a Windows troubleshooting assistant. Answer using ONLY the
CONTEXT below, drawn from a curated troubleshooting encyclopedia. If the
context doesn't fully cover the symptom, say so explicitly rather than
guessing. Cite entry IDs (e.g. V2.C3.E7000) for every claim.

USER SYMPTOM / ANOMALY:
{query}

CONTEXT (retrieved encyclopedia entries):
{context}

Respond in exactly this structure:
1. **Likely match** — which entry_id(s) best explain the symptom, and why.
2. **Root cause(s)** — ranked by prevalence, per the context.
3. **Recommended diagnostic steps** — in order, flagging any step that
   modifies the system before it's run.
4. **Recommended resolution** — the fix once the root cause is confirmed.
5. **Confidence & gaps** — what the context does NOT tell you, if anything.
"""
    return prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", help="Path to encyclopedia.db (from build_sqlite.py)")
    ap.add_argument("query", help="Symptom, event ID, or error code")
    ap.add_argument("--vecstore", default=None, help="Path to Chroma store (optional, for semantic search)")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--llm-prompt", action="store_true", help="Print a ready-to-send LLM prompt instead of JSON")
    args = ap.parse_args()

    results = retrieve(args.db, args.query, args.vecstore, args.top_k)

    if not results:
        print("No matching entries found. Try broader terms or check the entry_id directly.")
        return

    if args.llm_prompt:
        print(build_llm_prompt(args.query, results))
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
