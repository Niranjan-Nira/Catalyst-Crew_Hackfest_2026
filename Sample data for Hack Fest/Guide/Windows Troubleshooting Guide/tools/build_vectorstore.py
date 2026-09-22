#!/usr/bin/env python3
"""
build_vectorstore.py — Embed each entry and store vectors for semantic
retrieval. This is what lets a RAG pipeline match a *paraphrased* symptom
("machine won't stop rebooting unexpectedly") to the right entry even when it
shares no exact keywords with the corpus (which might say "unclean shutdown"
or "Kernel-Power 41").

Chunking strategy (important): one chunk PER ENTRY, not per paragraph. Each
entry is already a self-contained unit (~300-900 words) with its own frontmatter
metadata — splitting it further would separate a root cause from its
diagnostic procedure, breaking exactly the join a troubleshooting agent needs.
The only exception: entries over ~1500 words (rare in this corpus) get a
secondary "long-entry" split by section, tagged with a shared parent_entry_id
so retrieval can still surface the whole entry.

Two backends supported, pick with --backend:
  chroma     — persistent, batteries-included, recommended default.
               pip install chromadb sentence-transformers
  sqlite-vec — keeps everything in one .db file alongside build_sqlite.py's
               output; good if you want a single-file, no-server deployment.
               pip install sqlite-vec sentence-transformers

Embedding model: all-MiniLM-L6-v2 (sentence-transformers) by default — small,
fast, runs on CPU, no API key. Swap --model for a stronger one (e.g.
BAAI/bge-base-en-v1.5) if retrieval quality needs it; the code doesn't care.

Usage:
    python3 build_vectorstore.py /path/to/win-encyclopedia \
        --backend chroma --out ./chroma_store

    python3 build_vectorstore.py /path/to/win-encyclopedia \
        --backend sqlite-vec --out encyclopedia.db
"""
import argparse
from pathlib import Path

from parse_entries import parse_corpus


def build_embed_text(entry):
    """What actually gets embedded per entry. Includes title + overview +
    meaning + root causes + a symptom-oriented summary so a raw symptom query
    ('service won't start, access denied') has strong lexical+semantic overlap
    with the vector, not just the formal event-ID name."""
    s = entry.get("sections", {})
    parts = [
        entry.get("title", ""),
        s.get("Overview", ""),
        s.get("Meaning") or next((v for k, v in s.items() if k.startswith("Meaning")), ""),
        s.get("Likely Root Causes", ""),
        s.get("Impact", ""),
    ]
    return "\n\n".join(p for p in parts if p)


def get_embedder(model_name):
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)

    def embed(texts):
        return model.encode(texts, show_progress_bar=True, normalize_embeddings=True).tolist()
    return embed


def build_chroma(entries, out_dir, model_name):
    import chromadb

    embed = get_embedder(model_name)
    client = chromadb.PersistentClient(path=str(out_dir))
    coll = client.get_or_create_collection(
        name="windows_troubleshooting_encyclopedia",
        metadata={"hnsw:space": "cosine"},
    )

    ids, docs, metadatas = [], [], []
    for e in entries:
        ids.append(e["entry_id"])
        docs.append(build_embed_text(e))
        event = e.get("event") or {}
        metadatas.append({
            "title": e.get("title") or "",
            "category": e.get("category") or "",
            "severity_for_triage": e.get("severity_for_triage") or "",
            "event_id": str(event.get("id", "")),
            "event_provider": event.get("provider") or "",
            "status": e.get("status") or "",
        })

    vectors = embed(docs)
    # Chroma batches; keep it simple with one call since corpus is small (~171).
    coll.add(ids=ids, embeddings=vectors, documents=docs, metadatas=metadatas)
    return len(ids)


def build_sqlite_vec(entries, out_path, model_name):
    import sqlite3
    import sqlite_vec

    embed = get_embedder(model_name)
    docs = [build_embed_text(e) for e in entries]
    vectors = embed(docs)
    dim = len(vectors[0])

    conn = sqlite3.connect(out_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS entry_vectors USING vec0(
            entry_id TEXT PRIMARY KEY,
            embedding FLOAT[{dim}]
        )
    """)
    conn.execute("DELETE FROM entry_vectors")
    for e, vec in zip(entries, vectors):
        conn.execute(
            "INSERT INTO entry_vectors (entry_id, embedding) VALUES (?, ?)",
            (e["entry_id"], sqlite_vec.serialize_float32(vec)),
        )
    conn.commit()
    conn.close()
    return len(entries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Path to the win-encyclopedia directory")
    ap.add_argument("--backend", choices=["chroma", "sqlite-vec"], default="chroma")
    ap.add_argument("--out", required=True, help="Output directory (chroma) or .db file (sqlite-vec)")
    ap.add_argument("--model", default="all-MiniLM-L6-v2",
                     help="sentence-transformers model name")
    args = ap.parse_args()

    entries = parse_corpus(Path(args.root))
    print(f"Parsed {len(entries)} entries; embedding with {args.model} ...")

    if args.backend == "chroma":
        n = build_chroma(entries, Path(args.out), args.model)
    else:
        n = build_sqlite_vec(entries, args.out, args.model)

    print(f"Indexed {n} entry vectors into {args.out} (backend={args.backend})")


if __name__ == "__main__":
    main()
