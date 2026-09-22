import os
import re
import math
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Union

from ..config import (
    HACKATHON_GUIDE_PATH,
    CHEAT_SHEET_PATH,
    GUIDE_DIR,
    CATALOG_PATH,
    ANOMALY_GUIDE_PATH,
    METHODOLOGY_PATH,
    WER_GUIDE_PATH,
    START_GUIDE_PATH,
    INDEX_GUIDE_PATH,
    CUSTOM_DOCS_DIR,
    LABELED_DATA_DIR,
)
from .chunker import chunk_markdown_document, extract_metadata
from .parser import extract_text_from_file, extract_text_from_file_data


class RAGKnowledgeBase:
    """
    Comprehensive, multi-source RAG Knowledge Base.
    Indexes:
      1. HACKATHON_DATA_GUIDE.md (Tiers 1-4, Category Playbooks 3.1-3.5, Judging Criteria)
      2. Diagnostic Cheat Sheet.md (Plain English translations, Time Join Key, 3-Step Worksheet)
      3. How to read Crash Dumps_REPORT_WER.md (UTF-16LE, FILETIME, Sig signatures)
      4. Where to start across 17 folders.md (4-step funnel, presence = signal)
      5. ANOMALY_INVESTIGATION_GUIDE.md & COMMON_ANOMALY_CATALOG.md
      6. DATASET_METHODOLOGY.md & INDEX.md
      7. 10-Volume Windows Troubleshooting Guide (171 Chapters, Root Causes, PowerShell commands)
      8. User-added / Custom documents from knowledge_docs/ or dynamic API
    """

    def __init__(
        self,
        guide_dir: Optional[Path] = None,
        catalog_path: Optional[Path] = None,
        custom_docs_dir: Optional[Path] = None,
        use_semantic: bool = True
    ):
        self.guide_dir = Path(guide_dir) if guide_dir else GUIDE_DIR
        self.catalog_path = Path(catalog_path) if catalog_path else CATALOG_PATH
        self.custom_docs_dir = Path(custom_docs_dir) if custom_docs_dir else CUSTOM_DOCS_DIR
        self.use_semantic = use_semantic

        self.documents: List[Dict[str, Any]] = []
        self.indexed_files: Set[str] = set()
        self.file_chunk_counts: Dict[str, int] = {}
        self.file_hashes: Dict[str, str] = {}

        # BM25 Statistics
        self.doc_lengths: List[int] = []
        self.avg_doc_len: float = 0.0
        self.idf_cache: Dict[str, float] = {}

        # Semantic Embeddings
        self._embedder = None
        self._embeddings = None

        self._build_index()

    def _hash_content(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()

    def _index_file(
        self,
        file_path: Path,
        doc_type: str = "guide",
        doc_title: Optional[str] = None
    ) -> int:
        """Read and index a markdown or text file into the knowledge base."""
        if not file_path.exists():
            return 0

        try:
            text = extract_text_from_file(file_path)
            if not text or not text.strip():
                return 0

            text_hash = self._hash_content(text)
            norm_name = file_path.name
            if norm_name in self.file_hashes and self.file_hashes[norm_name] == text_hash:
                return 0  # Already indexed identical content

            chunks = chunk_markdown_document(
                text=text,
                source_file=file_path.name,
                doc_title=doc_title or file_path.stem.replace("_", " ").title(),
                doc_type=doc_type
            )

            if chunks:
                self.documents.extend(chunks)
                self.indexed_files.add(file_path.name)
                self.file_chunk_counts[file_path.name] = len(chunks)
                self.file_hashes[norm_name] = text_hash
                return len(chunks)
        except Exception as e:
            print(f"[RAG Indexer] Error indexing {file_path}: {e}")
        return 0

    def _build_index(self):
        """Indexes all default and configured knowledge sources."""
        self.documents = []
        self.indexed_files = set()
        self.file_chunk_counts = {}
        self.file_hashes = {}

        # 1. HACKATHON_DATA_GUIDE.md (Highest priority for hackathon rules & playbooks)
        if HACKATHON_GUIDE_PATH.exists():
            self._index_file(HACKATHON_GUIDE_PATH, doc_type="hackathon_guide", doc_title="Hackathon Data Guide")

        # 2. Diagnostic Cheat Sheet.md (Plain English translation & Time join key)
        if CHEAT_SHEET_PATH.exists():
            self._index_file(CHEAT_SHEET_PATH, doc_type="cheat_sheet", doc_title="Diagnostic Cheat Sheet")

        # 3. Crash Dumps & Report.wer Guide
        if WER_GUIDE_PATH.exists():
            self._index_file(WER_GUIDE_PATH, doc_type="wer_guide", doc_title="How to read Crash Dumps & Report.wer")

        # 4. Where to start across 17 folders
        if START_GUIDE_PATH.exists():
            self._index_file(START_GUIDE_PATH, doc_type="investigation_guide", doc_title="Where to start across 17 folders")

        # 5. Anomaly Investigation Guide
        if ANOMALY_GUIDE_PATH.exists():
            self._index_file(ANOMALY_GUIDE_PATH, doc_type="investigation_guide", doc_title="Anomaly Investigation Guide")

        # 6. Common Anomaly Catalog
        if self.catalog_path.exists():
            self._index_file(self.catalog_path, doc_type="anomaly_catalog", doc_title="Common Anomaly Catalog")

        # 7. Dataset Methodology
        if METHODOLOGY_PATH.exists():
            self._index_file(METHODOLOGY_PATH, doc_type="methodology", doc_title="Dataset Methodology")

        # 8. Index Guide
        if INDEX_GUIDE_PATH.exists():
            self._index_file(INDEX_GUIDE_PATH, doc_type="index_guide", doc_title="Participant Documentation Index")

        # 9. 10-Volume Windows Troubleshooting Guide
        if self.guide_dir.exists():
            for md_file in sorted(self.guide_dir.rglob("*.md")):
                # Avoid re-indexing READMEs that are purely navigational if they are tiny
                rel_path = md_file.relative_to(self.guide_dir)
                doc_title = f"Troubleshooting Encyclopedia: {rel_path.stem.replace('-', ' ').title()}"
                self._index_file(md_file, doc_type="troubleshooting_volume", doc_title=doc_title)

        # 10. Bundled labeled reference data. These are free, local evaluation
        # examples and must remain separate from live case-derived learnings.
        if LABELED_DATA_DIR.exists():
            for labeled_file in sorted(LABELED_DATA_DIR.glob("*.csv")):
                self._index_file(
                    labeled_file,
                    doc_type="labeled_reference_data",
                    doc_title=f"Labeled Reference: {labeled_file.stem}"
                )

        # 11. User-added / Custom Knowledge Documents (from knowledge_docs/)
        if self.custom_docs_dir.exists():
            for cust_file in sorted(self.custom_docs_dir.glob("*.*")):
                if cust_file.suffix.lower() in [".md", ".txt", ".csv", ".json", ".pdf", ".docx", ".doc"]:
                    self._index_file(cust_file, doc_type="custom_doc", doc_title=cust_file.stem)

        # Recompute BM25 corpus statistics
        self._recompute_bm25_stats()

    def _recompute_bm25_stats(self):
        """Precomputes BM25 document lengths, average document length, and IDF scores."""
        N = len(self.documents)
        if N == 0:
            return

        self.doc_lengths = [len(doc["tokens"]) for doc in self.documents]
        self.avg_doc_len = sum(self.doc_lengths) / max(N, 1)

        # Compute document frequency for each term
        doc_freq: Dict[str, int] = {}
        for doc in self.documents:
            for token in doc["tokens"]:
                doc_freq[token] = doc_freq.get(token, 0) + 1

        # Calculate Okapi BM25 IDF: ln((N - df + 0.5)/(df + 0.5) + 1)
        self.idf_cache = {}
        for token, df in doc_freq.items():
            self.idf_cache[token] = math.log(((N - df + 0.5) / (df + 0.5)) + 1.0)

    def add_document(
        self,
        content: Union[str, bytes],
        doc_name: str,
        doc_type: str = "custom_doc",
        save_to_disk: bool = True,
        raw_bytes: Optional[bytes] = None
    ) -> int:
        """
        Dynamically ingests a new document (text, markdown, PDF, Word DOCX/DOC)
        into the knowledge base at runtime.
        Optionally persists it to knowledge_docs/ for cross-session availability.
        """
        clean_name = re.sub(r"[^\w\-\.]", "_", doc_name)

        # Determine if content is raw bytes or text
        if isinstance(content, (bytes, bytearray)):
            raw_bytes = bytes(content)
            text = extract_text_from_file_data(raw_bytes, filename=clean_name)
        else:
            text = str(content)

        if not text or not text.strip():
            return 0

        # Determine persistence filename and format
        if save_to_disk:
            self.custom_docs_dir.mkdir(parents=True, exist_ok=True)
            if raw_bytes is not None:
                target_path = self.custom_docs_dir / clean_name
                target_path.write_bytes(raw_bytes)
            else:
                target_name = clean_name
                if not target_name.endswith(".md") and not target_name.endswith(".txt"):
                    target_name += ".md"
                target_path = self.custom_docs_dir / target_name
                target_path.write_text(text, encoding="utf-8")

        chunks = chunk_markdown_document(
            text=text,
            source_file=clean_name,
            doc_title=doc_name,
            doc_type=doc_type
        )

        if chunks:
            self.documents.extend(chunks)
            self.indexed_files.add(clean_name)
            self.file_chunk_counts[clean_name] = self.file_chunk_counts.get(clean_name, 0) + len(chunks)
            self.file_hashes[clean_name] = self._hash_content(text)
            self._recompute_bm25_stats()
            # Invalidate semantic cache if embeddings are active
            self._embeddings = None
            return len(chunks)
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistical overview of the active knowledge base."""
        categories = {}
        doc_types = {}
        for doc in self.documents:
            cat = doc.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
            dt = doc.get("doc_type", "guide")
            doc_types[dt] = doc_types.get(dt, 0) + 1

        total_storage_bytes = sum(len(doc.get("content", "").encode("utf-8", errors="ignore")) for doc in self.documents)
        if total_storage_bytes >= 1024 * 1024:
            formatted_size = f"{total_storage_bytes / (1024 * 1024):.2f} MB"
        else:
            formatted_size = f"{total_storage_bytes / 1024:.1f} KB"

        return {
            "total_documents": len(self.indexed_files),
            "total_chunks": len(self.documents),
            "total_storage_bytes": total_storage_bytes,
            "formatted_storage_size": formatted_size,
            "categories": categories,
            "doc_types": doc_types,
            "files": self.file_chunk_counts,
            "avg_tokens_per_chunk": int(self.avg_doc_len)
        }

    def get_semantic_model(self):
        """Lazily load SentenceTransformer model if available."""
        if not self.use_semantic:
            return None
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                print(f"[RAG Indexer] Semantic model not loaded (falling back to lexical BM25): {e}")
                self._embedder = False
        return self._embedder if self._embedder is not False else None
