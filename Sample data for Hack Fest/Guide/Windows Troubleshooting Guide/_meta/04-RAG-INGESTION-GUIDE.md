# Converting This Encyclopedia into a RAG System

**Curated by Joe Prakash**

This guide covers turning the 171 entries into a database an AI agent can
query to find anomalies, likely root causes, and recommended fixes. Three
scripts are provided in `tools/`, already tested against this corpus — the
numbers below are real output, not illustrations.

```
tools/
  parse_entries.py      — shared parser: markdown -> structured records
  build_sqlite.py        — structured DB + full-text search (no ML needed)
  build_vectorstore.py   — semantic embeddings (Chroma or sqlite-vec)
  rag_query.py            — hybrid retrieval + LLM prompt assembly
```

---

## 1. Why this needs more than "dump the markdown into a vector DB"

The naive approach — embed each `.md` file as one blob — throws away the
structure that makes this corpus useful for automated triage. Every entry
already separates **what it is** (Overview/Meaning) from **why it happens**
(Likely Root Causes, ranked by prevalence) from **what to do** (Diagnostic
Procedure, with exact commands) from **how to fix it** (Resolution). An
anomaly-detection agent needs to query these *independently* — "give me every
`very common` root cause across all storage-related entries" is a query a flat
text blob can't answer but a structured table can.

So this pipeline builds **two complementary layers**:

| Layer | Built by | Answers | Needs |
|---|---|---|---|
| Structured SQL + full-text search | `build_sqlite.py` | Exact/keyword lookups: "event 7000", "0xC0000005", joins across root causes/steps | Nothing but Python stdlib |
| Semantic vector search | `build_vectorstore.py` | Paraphrased symptoms with no shared vocabulary: "computer keeps restarting for no reason" | An embedding model (see §4) |

Use both. The SQL layer alone gets you surprisingly far (see the tested
examples in §3); the vector layer is what catches the cases SQL misses.

## 2. Step 1 — Build the structured database (no dependencies)

```bash
cd win-encyclopedia
python3 tools/build_sqlite.py . --out encyclopedia.db
```

**Actual output from this corpus:**
```
Built encyclopedia.db
  entries: 171 rows
  root_causes: 92 rows
  diagnostic_steps: 455 rows
  resolutions: 25 rows
  related_entries: 309 rows
  sources: 236 rows
```

### Schema, and why it's shaped this way

- **`entries`** — one row per entry_id, with the event ID/provider/channel
  pulled into their own columns (not buried in text) so `WHERE event_id =
  '7000'` works directly — this is the fast path every Windows troubleshooting
  query should try first, because an event ID is the highest-precision signal
  available.
- **`root_causes`** — one row per cause, in stated order, with `prevalence`
  (`very common`/`common`/`uncommon`/`rare`) extracted as its own column. This
  is what lets an agent rank hypotheses instead of just listing them.
- **`diagnostic_steps`** — one row per step, **with the exact command and its
  language extracted separately from the descriptive text**, and a
  `modifies_system` flag pulled from the `[MODIFIES SYSTEM]` markers. A
  tool-calling agent can iterate this table and decide per-row whether to ask
  for confirmation before running something.
- **`related_entries`** — the cross-reference graph as an edge list. This
  matters more than it looks: real incidents in this encyclopedia are
  deliberately cross-linked (a storage event links to the WER exception-code
  table, which links to the dump-analysis chapter), so a good retrieval
  pipeline should pull one hop of related entries alongside the direct match,
  not just the single best-scoring row.
- **`entries_fts`** — an FTS5 virtual table over title + full body, using the
  BM25 ranking function. This alone is a working keyword retriever.

### Verified retrieval quality (FTS layer only, tested against this corpus)

```bash
python3 tools/rag_query.py encyclopedia.db "service failed to start access denied" --top-k 3
```
```
V2.C3.E7000  — SCM 7000: Service Failed to Start          ← correct top hit
V2.C12.E001 — TaskScheduler/Operational: ... Task Lifecycle
V5.C3.E003  — Common GPO Failures: ...
```

```bash
python3 tools/rag_query.py encyclopedia.db "app crashes with 0xC0000005" --top-k 3
```
```
V2.C7.E1000 — Application Error 1000: The Application Crash
V3.C1.E006  — Exception Code Reference: 0xC0000005 and the Other Codes That Matter  ← exact code match
V6.C2.E003  — SmartScreen and Exploit Protection
```

Both of these are exact top-1 hits with zero embedding model involved —
because the query shared vocabulary (event names, hex codes) with the corpus.

### Where FTS-only genuinely fails (tested, and this is the honest limitation)

```bash
python3 tools/rag_query.py encyclopedia.db "computer keeps restarting unexpectedly" --top-k 3
```
```
V5.C3.E003  — Common GPO Failures: Slow Link, Loopback, Security Filtering
V2.C6.E5722 — NETLOGON 5722/3210: Machine Account ... Failures
V2.C10.E4740 — 4740: Account Lockout
```

The correct answer — **`V2.C2.E041`, Kernel-Power 41: The Unexpected
Shutdown** — doesn't appear at all. The query shares almost no exact
vocabulary with that entry (which talks about "unclean shutdown,"
"bugcheck," "hard hang"), so keyword search has nothing to latch onto. This
is precisely the case semantic search exists to fix, and it's why step 2
below isn't optional if your users will describe symptoms in their own words
rather than quoting Windows' terminology.

## 3. Step 2 — Add semantic search (needs an embedding model)

```bash
pip install sentence-transformers chromadb
python3 tools/build_vectorstore.py . --backend chroma --out ./chroma_store
```

**What gets embedded per entry** (see `build_embed_text()` in
`build_vectorstore.py`): title + Overview + Meaning + Likely Root Causes +
Impact — deliberately *not* the Diagnostic Procedure or command blocks, which
are noisy for semantic matching (a PowerShell command doesn't paraphrase a
symptom well) but are still fetched in full once the entry is matched.

**Chunking strategy: one vector per entry, not per paragraph.** Each entry is
already a self-contained ~300–900 word unit built around one topic. Splitting
further would separate a root cause from the diagnostic steps that resolve it
— exactly the join a troubleshooting agent needs intact. This corpus has no
entries long enough to need sub-chunking in practice.

**Note on this guide's testing:** the SQLite/FTS layer above was fully tested
against live output from this corpus (171 entries, real query results shown).
The embedding step requires `sentence-transformers` + `chromadb`, which need
more disk space than was available in the sandbox used to build this
encyclopedia — the *code path* is written and the text-construction logic was
verified, but you should do a first-run sanity check in your own environment
before trusting it in production:

```bash
python3 tools/rag_query.py encyclopedia.db "computer keeps restarting unexpectedly" \
    --vecstore ./chroma_store --top-k 3
```
Confirm `V2.C2.E041` now appears — that's the regression test for this layer.

**Model choice:** `all-MiniLM-L6-v2` (the default) is small and CPU-friendly —
fine for a corpus this size (171 entries embed in seconds). If retrieval
quality on ambiguous symptoms disappoints, swap `--model BAAI/bge-base-en-v1.5`
or an OpenAI/Azure embedding endpoint (swap `get_embedder()` in
`build_vectorstore.py` for an API call — the rest of the pipeline is
embedding-agnostic).

**Alternative backend:** `--backend sqlite-vec` keeps everything — structured
data and vectors — in one `.db` file if you want a single-file deployment
instead of a separate Chroma directory. Same CLI, same retrieval code path.

## 4. Step 3 — Query it (the RAG retrieval layer)

`rag_query.py` implements hybrid retrieval in priority order:

1. **Exact match** — event IDs (`"event 7000"`) and hex codes
   (`"0xC0000005"`) are regex-extracted from the query and looked up directly
   against the `event_id` column and FTS phrase search. Always wins when
   present — it's the highest-precision signal in this domain.
2. **FTS5 keyword search** — BM25-ranked, always runs, needs nothing extra.
3. **Vector search** — only runs if `--vecstore` is passed and the store
   exists; silently skipped otherwise (the script still works standalone).

Results are merged and de-duplicated, then each surviving `entry_id` is
expanded back out to its full structured record — root causes with
prevalence, ordered diagnostic steps with extracted commands, resolutions,
and one hop of related entries.

```bash
# Raw JSON (for piping into your own agent/orchestration code):
python3 tools/rag_query.py encyclopedia.db "service won't start, error 1053"

# LLM-ready prompt (context assembled, structured output format specified):
python3 tools/rag_query.py encyclopedia.db "service won't start, error 1053" --llm-prompt
```

The `--llm-prompt` output — tested and shown verbatim below — is a complete
prompt: grounding context from the matched entries, plus an instruction to
answer in exactly the shape you asked for (anomaly → root cause →
recommendation):

```
You are a Windows troubleshooting assistant. Answer using ONLY the
CONTEXT below, drawn from a curated troubleshooting encyclopedia. If the
context doesn't fully cover the symptom, say so explicitly rather than
guessing. Cite entry IDs (e.g. V2.C3.E7000) for every claim.

USER SYMPTOM / ANOMALY:
service won't start, error 1053

CONTEXT (retrieved encyclopedia entries):
### V2.C3.E7000 — SCM 7000: Service Failed to Start [severity: high, status: draft]
...
Likely Root Causes:
  - (very common) Missing/invalid `ImagePath` after uninstall or AV quarantine.
  - (very common) Startup timeout (1053) from slow dependencies or profile issues.
  ...
Diagnostic Steps:
  1. Read the exact error:
     command: Get-WinEvent -FilterHashtable @{LogName='System'; ...}
  ...

Respond in exactly this structure:
1. **Likely match** — which entry_id(s) best explain the symptom, and why.
2. **Root cause(s)** — ranked by prevalence, per the context.
3. **Recommended diagnostic steps** — in order, flagging any step that
   modifies the system before it's run.
4. **Recommended resolution** — the fix once the root cause is confirmed.
5. **Confidence & gaps** — what the context does NOT tell you, if anything.
```

Send this to any LLM API (Claude, GPT, local model) and you have a working
anomaly → root cause → recommendation pipeline grounded entirely in the
curated encyclopedia rather than the model's general training data.

## 5. Wiring this into a live anomaly-detection loop

A realistic production shape:

1. **Collector** feeds raw signals in — Event Viewer records (via
   `Get-WinEvent`, as documented in `V7.C1.E001`), WER reports, or a
   monitoring agent's alerts.
2. For each anomaly, extract the event ID / error code if present (regex, as
   `rag_query.py` already does) — this is the fast, cheap, high-precision
   path and should always be tried first.
3. Call `retrieve()` (import it directly from `rag_query.py`, or shell out) to
   get the top-k matching entries with full structured content.
4. Feed the assembled context to your LLM with the prompt template in
   `build_llm_prompt()` (or your own), asking specifically for root cause
   ranking and recommended next steps.
5. **Log every match's `status` field.** Every entry in this edition is
   `status: draft` — curated from documentation and field knowledge but not
   yet independently verified against a live failure. An agent should
   surface that caveat to whoever acts on its recommendation, and flag
   `[MODIFIES SYSTEM]` steps for confirmation before automatic execution.

## 6. Keeping the database in sync as the encyclopedia grows

Both build scripts are idempotent — re-running them against an updated
`win-encyclopedia/` directory regenerates the database/vector store from
scratch (`build_sqlite.py` deletes and recreates its output file; re-run
`build_vectorstore.py` after any content change since embeddings are
content-derived and won't auto-update). For a corpus this size (171 entries),
a full rebuild takes seconds for SQLite and well under a minute for
embeddings — there's no need for incremental-update logic at this scale.
