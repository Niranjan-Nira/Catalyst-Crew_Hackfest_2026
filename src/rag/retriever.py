import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Union

from .indexer import RAGKnowledgeBase

_global_kb: Optional[RAGKnowledgeBase] = None


def get_knowledge_base() -> RAGKnowledgeBase:
    """Returns or initializes the singleton RAGKnowledgeBase."""
    global _global_kb
    if _global_kb is None:
        _global_kb = RAGKnowledgeBase()
    return _global_kb


def add_custom_document(
    content: Union[str, bytes],
    doc_name: str,
    doc_type: str = "custom_doc",
    save_to_disk: bool = True,
    raw_bytes: Optional[bytes] = None
) -> int:
    """Convenience helper to add a document (text, markdown, PDF, Word DOCX/DOC) to the global knowledge base."""
    kb = get_knowledge_base()
    return kb.add_document(content, doc_name, doc_type=doc_type, save_to_disk=save_to_disk, raw_bytes=raw_bytes)


# --- Advanced Technique 1: Domain Query Expansion ---
DOMAIN_QUERY_EXPANSIONS: Dict[str, List[str]] = {
    "blue screen": ["BugCheck", "0x0000003B", "0x0000001A", "0x00000050", "Kernel-Power", "41"],
    "bsod": ["BugCheck", "Kernel-Power", "41", "Minidump", "LiveKernelReports"],
    "freezing": ["AppHang", "MoAppHang", "LiveKernelEvent", "WATCHDOG", "0x193", "0x1A8", "TDR", "4101"],
    "freeze": ["AppHang", "MoAppHang", "LiveKernelEvent", "WATCHDOG", "0x193", "0x1A8", "TDR", "4101"],
    "laptop freezing": ["LiveKernelEvent", "WATCHDOG", "AppHang", "TDR", "0x193", "0x1A8"],
    "docking": ["Intel-Gfx-Display-External", "10", "EDID", "dock", "PnP", "CM_PROB_FAILED_POST_START"],
    "monitor": ["Intel-Gfx-Display-External", "10", "EDID", "display", "resolution"],
    "external display": ["Intel-Gfx-Display-External", "10", "docking", "EDID"],
    "wifi": ["WLAN-AutoConfig", "8003", "8002", "8000", "Netwtw08", "Netwtw10", "NDIS"],
    "wifi dropping": ["WLAN-AutoConfig", "8003", "8002", "Netwtw10", "roaming"],
    "memory leak": ["MemoryAvailableMB", "TopProcesses_PerSample", "working set", "leak", "monotonic"],
    "high memory": ["MemoryAvailableMB", "TopMemoryProcesses", "working set", "RAM"],
    "office crash": ["OFFICE_MODULE_VERSION_MISMATCH", "Click-to-Run", "Sig[1].Value", "PowerPoint", "AppCrash"],
    "powerpoint crash": ["OFFICE_MODULE_VERSION_MISMATCH", "Click-to-Run", "POWERPNT", "AppCrash"],
    "driver failed": ["CM_PROB_FAILED_START", "CM_PROB_FAILED_POST_START", "pnputil", "Device Manager"],
    "code 10": ["CM_PROB_FAILED_START", "PnP", "Device Manager", "bthserv"],
    "service crash": ["7000", "7009", "7034", "Service Control Manager", "SCM", "timeout"],
    "disk high": ["153", "Storport", "Disk", "retry", "IO timeout", "SMART"],
    "overheating": ["TemperatureCelsius", "thermal", "throttling", "SSD", "SMART"],
    "shutdown": ["Kernel-Power", "41", "Fast Startup", "HiberbootEnabled", "dirty shutdown"]
}


def expand_query_with_domain_knowledge(query: str) -> str:
    """
    Expands conversational user queries with authoritative Windows diagnostic keywords,
    Event IDs, hex stop codes, and WER signatures.
    """
    low_q = query.lower()
    expansions = []
    for trigger, terms in DOMAIN_QUERY_EXPANSIONS.items():
        if trigger in low_q:
            expansions.extend(terms)
    if expansions:
        # Deduplicate while preserving order
        seen = set(query.split())
        unique_adds = [t for t in expansions if t not in seen and not seen.add(t)]
        if unique_adds:
            return f"{query} {' '.join(unique_adds[:6])}"
    return query


def _find_multihop_related_chunk(
    doc: Dict[str, Any], kb: RAGKnowledgeBase
) -> Optional[Dict[str, Any]]:
    """
    Multi-Hop Knowledge Graph Traversal:
    Discovers 1-hop related entries (e.g. cross-volume references, related codes,
    resolution runbooks) referenced within this document's text or breadcrumb.
    """
    content = doc.get("content", "")
    # Search for cross-references like V3.C1.E006, V2.C7.E1000, Event 1000, 0xC0000005
    ref_patterns = re.findall(r"\b(V\d+\.C\d+\.E\d{3,4}|0x[0-9A-Fa-f]{8}|Event\s+\d{4,5})\b", content)
    if not ref_patterns:
        return None

    # Search knowledge base for the referenced identifier
    target_ref = ref_patterns[0].strip()
    target_ref_clean = target_ref.replace("Event ", "").strip()

    for other_doc in kb.documents:
        if other_doc["id"] == doc["id"]:
            continue
        other_content = other_doc.get("content", "")
        other_title = other_doc.get("section_title", "")
        if target_ref in other_title or target_ref in other_content or target_ref_clean in other_doc.get("hex_codes", []):
            return {
                "id": other_doc["id"],
                "doc_title": other_doc["doc_title"],
                "title": other_doc["section_title"],
                "source": other_doc["source"],
                "reference_key": target_ref,
                "summary": other_doc["content"][:240] + "..."
            }
    return None


def retrieve_grounded_context(
    query: str,
    top_k: int = 4,
    category: Optional[str] = None,
    doc_type: Optional[str] = None,
    use_expansion: bool = True,
    include_multihop: bool = True
) -> List[Dict[str, Any]]:
    """
    Advanced Multi-stage Hybrid Retrieval Engine:
      1. Domain Query Expansion (colloquial symptoms -> technical telemetry keys)
      2. Exact pattern fast-path (Event IDs, Hex codes, WER buckets, ConfigManager codes)
      3. Okapi BM25 keyword ranking with section and document title boosting
      4. Semantic vector matching (via SentenceTransformers all-MiniLM-L6-v2)
      5. Reciprocal Rank Fusion (RRF) & Multi-Hop Graph Traversal
    """
    kb = get_knowledge_base()
    if not query or not query.strip() or not kb.documents:
        return []

    clean_query = query.strip()
    effective_query = expand_query_with_domain_knowledge(clean_query) if use_expansion else clean_query
    low_query = effective_query.lower()

    # -------------------------------------------------------------
    # 1. EXTRACT QUERY SIGNALS (Event IDs, Hex codes, Buckets, etc.)
    # -------------------------------------------------------------
    query_eids = set(re.findall(r"\b(?:event\s*(?:id)?[:#]?\s*|id[:=\s]+)?(\d{2,6})\b", low_query))
    query_hex = set(m.upper() for m in re.findall(r"\b0x[0-9A-Fa-f]{2,8}\b", effective_query))
    query_config = set(m.upper() for m in re.findall(r"\bCM_PROB_[A-Z0-9_]+\b", effective_query, re.IGNORECASE))
    query_wer = set(m.upper() for m in re.findall(
        r"\b(APPCRASH|AppHang|OFFICE_MODULE_VERSION_MISMATCH|LiveKernelEvent|CLR20r3|BEX64|MoAppHang)\b",
        effective_query, re.IGNORECASE
    ))

    # Query tokens for BM25
    raw_tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", low_query)
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "what", "which",
        "how", "are", "was", "were", "been", "have", "has", "had", "can",
        "could", "should", "would", "about", "into", "through", "during"
    }
    query_tokens = [t for t in raw_tokens if t not in stopwords]

    scored_candidates = []

    k1 = 1.5
    b = 0.75
    avgdl = kb.avg_doc_len if kb.avg_doc_len > 0 else 100.0

    for idx, doc in enumerate(kb.documents):
        # Optional category or doc_type filter
        if category and category.lower() != "all" and doc.get("category") != category:
            continue
        if doc_type and doc_type.lower() != "all" and doc.get("doc_type") != doc_type:
            continue

        doc_score = 0.0
        match_reasons = []

        # --- Exact Signal Match (Fast Path) ---
        # A. Hex code exact match (e.g. 0xC0000005)
        if query_hex:
            matched_hex = query_hex.intersection(set(doc.get("hex_codes", [])))
            if matched_hex:
                doc_score += 45.0 * len(matched_hex)
                match_reasons.append(f"Exact Hex Code ({', '.join(matched_hex)})")

        # B. Event ID exact match (e.g. Event 7000, 41, 1000)
        if query_eids:
            matched_eids = query_eids.intersection(set(doc.get("event_ids", [])))
            if matched_eids:
                doc_score += 40.0 * len(matched_eids)
                match_reasons.append(f"Exact Event ID ({', '.join(matched_eids)})")

        # C. ConfigManager error code match (e.g. CM_PROB_FAILED_POST_START)
        if query_config:
            matched_cfg = query_config.intersection(set(doc.get("config_codes", [])))
            if matched_cfg:
                doc_score += 40.0 * len(matched_cfg)
                match_reasons.append(f"ConfigManager Code ({', '.join(matched_cfg)})")

        # D. WER Bucket match (e.g. OFFICE_MODULE_VERSION_MISMATCH)
        if query_wer:
            matched_wer = query_wer.intersection(set(doc.get("wer_buckets", [])))
            if matched_wer:
                doc_score += 35.0 * len(matched_wer)
                match_reasons.append(f"WER Bucket ({', '.join(matched_wer)})")

        # --- Okapi BM25 Keyword Search ---
        doc_tokens = doc["tokens"]
        doc_len = len(doc_tokens)
        title_low = doc.get("section_title", "").lower()
        doc_title_low = doc.get("doc_title", "").lower()

        bm25_score = 0.0
        matched_terms = 0

        for token in query_tokens:
            if token in doc_tokens:
                matched_terms += 1
                idf = kb.idf_cache.get(token, 1.0)
                tf = doc["content"].lower().count(token)
                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (doc_len / avgdl))
                term_score = idf * (numerator / max(denominator, 0.001))

                # Title boost (3.5x)
                if token in title_low or token in doc_title_low:
                    term_score *= 3.5

                bm25_score += term_score

        if matched_terms > 0:
            doc_score += bm25_score
            match_reasons.append(f"BM25 ({matched_terms} hits)")

        if doc_score > 0.5:
            scored_candidates.append({
                "score": doc_score,
                "doc": doc,
                "match_reasons": match_reasons,
                "idx": idx
            })

    # --- Semantic Rescoring (SentenceTransformers) ---
    embedder = kb.get_semantic_model()
    if embedder and scored_candidates:
        try:
            scored_candidates.sort(key=lambda x: x["score"], reverse=True)
            top_eval = scored_candidates[:25]

            query_vec = embedder.encode(clean_query, normalize_embeddings=True)
            doc_texts = [f"{c['doc']['doc_title']}: {c['doc']['section_title']} - {c['doc']['content'][:300]}" for c in top_eval]
            doc_vecs = embedder.encode(doc_texts, normalize_embeddings=True)

            for i, cand in enumerate(top_eval):
                cosine_sim = float(query_vec @ doc_vecs[i])
                if cosine_sim > 0.35:
                    cand["score"] += cosine_sim * 25.0
                    cand["match_reasons"].append(f"Semantic Cosine ({cosine_sim:.2f})")
        except Exception:
            pass

    # Sort candidates by combined score descending
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    # Return top_k formatted results with multi-hop references
    results = []
    seen_contents = set()

    for item in scored_candidates:
        doc = item["doc"]
        content_hash = doc["id"]
        if content_hash in seen_contents:
            continue
        seen_contents.add(content_hash)

        # Highlight snippet
        content = doc["content"]
        snippet = content[:320] + "..." if len(content) > 320 else content

        # Multi-Hop Graph Traversal
        multihop_info = None
        if include_multihop:
            multihop_info = _find_multihop_related_chunk(doc, kb)

        results.append({
            "id": doc["id"],
            "source": doc["source"],
            "doc_title": doc["doc_title"],
            "doc_type": doc["doc_type"],
            "title": doc["section_title"],
            "breadcrumb": doc["breadcrumb"],
            "category": doc["category"],
            "content": content,
            "snippet": snippet,
            "score": round(item["score"], 2),
            "match_reasons": item["match_reasons"],
            "event_ids": doc.get("event_ids", []),
            "hex_codes": doc.get("hex_codes", []),
            "wer_buckets": doc.get("wer_buckets", []),
            "multihop_reference": multihop_info,
            "expanded_query_used": effective_query if effective_query != clean_query else None
        })

        if len(results) >= top_k:
            break

    return results


def build_llm_prompt(query: str, results: List[Dict[str, Any]]) -> str:
    """
    Builds a complete, grounded LLM prompt compliant with HACKATHON_DATA_GUIDE.md
    demanding 4 explicit tiers, evidence citation, and confidence justification.
    """
    context_blocks = []
    for r in results:
        context_blocks.append(
            f"### [{r['doc_title']}] {r['title']} (Source: {r['source']}, Category: {r['category']})\n"
            f"{r['content']}"
        )
    context_text = "\n\n---\n\n".join(context_blocks)

    return f"""You are an enterprise Windows diagnostics and root cause analysis expert.
Answer the user's symptom / investigation query using ONLY the verified CONTEXT below, drawn from the official Hackathon Data Guide, Diagnostic Cheat Sheet, and Windows Troubleshooting Encyclopedia.

RULES PER HACKATHON_DATA_GUIDE.md:
1. Every claim or finding MUST cite its specific source document (e.g. `HACKATHON_DATA_GUIDE.md §3.1`, `Diagnostic Cheat Sheet.md Step 2`).
2. Clearly separate findings into the 4 explicit tiers if applicable:
   - Tier 1: Anomalies (High confidence, clear corroborated evidence)
   - Tier 2: Possible Anomalies (Moderate confidence, needs more data)
   - Tier 3: Root Causes (Evidence chain, confidence %, specific recommended action)
   - Tier 4: Possible Root Causes (Hypothesis, what's missing, what would confirm it)
3. Confidence percentages must be justified with a one-sentence rationale.
4. Recommended actions must be concrete and actionable (e.g. exact PowerShell command or rollback step).

USER QUERY / SYMPTOM:
{query}

GROUNDED CONTEXT:
{context_text}

RESPONSE:
"""
