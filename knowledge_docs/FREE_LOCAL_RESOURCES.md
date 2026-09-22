# Approved Free and Local Resources

This project uses local files and open-source packages for the demo. Luna is
the only optional network model endpoint.

## Free data sources already included

- `Input file/`: synthetic endpoint collection across the 17 diagnostic modules.
- `Sample data for Hack Fest/Dataset & Reference Materials/labeled_by_category/`:
  labeled anomaly, possible-anomaly, and normal reference examples.
- `knowledge_docs/`: investigation guides, methodology, anomaly catalog, and
  troubleshooting references.
- `Input file/02_EventLogs/CSV_Readable/`: readable event-log exports.
- `Input file/15_CrashDumps_WER/`: UTF-16 WER reports and dump inventory.
- `Input file/_StatusReport/`: collection-quality and phase-status metadata.

## Free local analysis resources

- Python standard library, pandas, and the existing parsers for structured log
  analysis.
- SentenceTransformers with `all-MiniLM-L6-v2` for local semantic retrieval.
- Local BM25 retrieval as an offline fallback.
- The existing statistical detectors for CPU, memory, temporal, and recurrence
  signals.
- Windows-native WinDbg and PowerShell tools when available on the demo laptop.

## Network policy

- Do not add Reddit, OpenAI, hosted vector databases, or another LLM endpoint.
- Luna may be used for optional RCA narrative generation when configured.
- Deterministic local diagnosis, local RAG, and local fallback behavior must
  remain fully usable without network access.

## Data-governance rule

The labeled reference files are indexed as immutable reference knowledge.
Accepted case RCAs are stored separately as `validated_rca` documents. Raw
case logs are never automatically added to the global knowledge base.