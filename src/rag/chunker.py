import re
from typing import List, Dict, Any, Optional

# Regular expressions for entity extraction
EVENT_ID_PATTERNS = [
    re.compile(r"\bevent\s*(?:id)?\s*[:#]?\s*(\d{1,6})\b", re.IGNORECASE),
    re.compile(r"\bId[=:\s]+(\d{1,6})\b", re.IGNORECASE),
    re.compile(r"Event ID\s+(\d{1,6})\b", re.IGNORECASE),
    re.compile(r"V\d+\.C\d+\.E(\d{1,6})\b", re.IGNORECASE),
]

HEX_CODE_RE = re.compile(r"\b0x[0-9A-Fa-f]{2,8}\b")
CONFIG_CODE_RE = re.compile(r"\bCM_PROB_[A-Z0-9_]+\b")
WER_BUCKET_RE = re.compile(
    r"\b(APPCRASH|AppHang|OFFICE_MODULE_VERSION_MISMATCH|LiveKernelEvent|CLR20r3|BEX64|MoAppHang|Kernel_[A-Za-z0-9_]+)\b",
    re.IGNORECASE
)
PROCESS_RE = re.compile(r"\b[A-Za-z0-9_\-]{2,30}\.(?:exe|dll|sys)\b", re.IGNORECASE)

CATEGORY_KEYWORDS = {
    "Crash / WER": ["crash", "hang", "appcrash", "wer", "bex64", "clr20r3", "exception", "faulting", "dump", "minidump"],
    "Hardware / Driver": ["driver", "hardware", "device", "configmanager", "cm_prob", "pnp", "peripheral", "bluetooth", "pci", "i219"],
    "Memory": ["memory", "ram", "whea", "working set", "leak", "page fault", "pool", "commit"],
    "CPU / Thermal": ["cpu", "thermal", "throttling", "temperature", "overheating", "core", "fan", "powercfg"],
    "Disk / Storage": ["disk", "drive", "storage", "smart", "ntfs", "chkdsk", "storport", "free space", "sector"],
    "Network": ["network", "wifi", "ethernet", "wlan", "adapter", "dns", "vpn", "disconnect", "ping", "latency"],
    "Investigation Playbook": ["funnel", "investigate", "lead", "presence = signal", "step 1", "step 2", "worksheet", "triage"],
    "Methodology / Rules": ["tier 1", "tier 2", "tier 3", "tier 4", "confidence", "judging", "rubric", "evidence chain", "threshold"],
    "Diagnostic Cheat Sheet": ["cheat sheet", "plain english", "translate", "join key", "red flag", "score dropped"]
}


def extract_metadata(text: str, doc_name: str, section_title: str) -> Dict[str, Any]:
    """Extract domain entities and infer category for a text chunk."""
    combined_text = f"{doc_name} {section_title} {text}"
    low_text = combined_text.lower()

    # 1. Event IDs
    event_ids = set()
    for pat in EVENT_ID_PATTERNS:
        for m in pat.finditer(combined_text):
            event_ids.add(m.group(1))

    # 2. Hex Codes
    hex_codes = set(m.group(0).upper() for m in HEX_CODE_RE.finditer(combined_text))

    # 3. ConfigManager Codes
    config_codes = set(m.group(0).upper() for m in CONFIG_CODE_RE.finditer(combined_text))

    # 4. WER Buckets
    wer_buckets = set(m.group(0).upper() for m in WER_BUCKET_RE.finditer(combined_text))

    # 5. Process / Module Names
    processes = set(m.group(0).lower() for m in PROCESS_RE.finditer(combined_text))

    # 6. Infer Category
    category_scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(low_text.count(kw) for kw in kws)
        if score > 0:
            category_scores[cat] = score

    if "cheat sheet" in doc_name.lower() or "cheat sheet" in low_text:
        inferred_category = "Diagnostic Cheat Sheet"
    elif "hackathon_data_guide" in doc_name.lower():
        if "tier" in low_text or "judging" in low_text or "expected output" in low_text:
            inferred_category = "Methodology / Rules"
        elif category_scores:
            inferred_category = max(category_scores.items(), key=lambda x: x[1])[0]
        else:
            inferred_category = "Investigation Playbook"
    elif category_scores:
        inferred_category = max(category_scores.items(), key=lambda x: x[1])[0]
    else:
        inferred_category = "General Windows Troubleshooting"

    # Token extraction for keyword search
    tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", low_text))

    return {
        "event_ids": sorted(list(event_ids)),
        "hex_codes": sorted(list(hex_codes)),
        "config_codes": sorted(list(config_codes)),
        "wer_buckets": sorted(list(wer_buckets)),
        "processes": sorted(list(processes)),
        "category": inferred_category,
        "tokens": tokens,
    }


def chunk_markdown_document(
    text: str,
    source_file: str,
    doc_title: Optional[str] = None,
    doc_type: str = "guide"
) -> List[Dict[str, Any]]:
    """
    Intelligently splits markdown text by headers (#, ##, ###) while preserving
    tables, code blocks, lists, and context breadcrumbs.
    """
    chunks = []
    lines = text.splitlines()

    # Detect H1 title if not provided
    if not doc_title:
        for line in lines[:10]:
            if line.startswith("# "):
                doc_title = line[2:].strip()
                break
        if not doc_title:
            doc_title = source_file.split("/")[-1].replace(".md", "")

    # Regex for header lines: e.g. # Header, ## Header, ### Header
    header_pattern = re.compile(r"^(#{1,3})\s+(.+?)$")

    current_section = doc_title
    current_lines = []
    breadcrumb = [doc_title]

    def flush_chunk():
        nonlocal current_lines, current_section, breadcrumb
        content = "\n".join(current_lines).strip()
        if content and len(content) >= 25:
            meta = extract_metadata(content, doc_title, current_section)
            chunk_id = f"{source_file}#{len(chunks) + 1}"
            chunks.append({
                "id": chunk_id,
                "source": source_file,
                "doc_title": doc_title,
                "doc_type": doc_type,
                "title": current_section,
                "section_title": current_section,
                "breadcrumb": " > ".join(breadcrumb),
                "content": content,
                "category": meta["category"],
                "event_ids": meta["event_ids"],
                "hex_codes": meta["hex_codes"],
                "config_codes": meta["config_codes"],
                "wer_buckets": meta["wer_buckets"],
                "processes": meta["processes"],
                "tokens": meta["tokens"],
                "length": len(content)
            })
        current_lines = []

    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            current_lines.append(line)
            continue

        if not in_code_block:
            header_match = header_pattern.match(line)
            if header_match:
                # Flush previous content
                if current_lines:
                    flush_chunk()

                level = len(header_match.group(1))
                heading_text = header_match.group(2).strip()
                current_section = heading_text

                # Adjust breadcrumb based on header level
                if level == 1:
                    breadcrumb = [doc_title, heading_text]
                elif level == 2:
                    breadcrumb = [doc_title, heading_text]
                elif level == 3:
                    if len(breadcrumb) >= 2:
                        breadcrumb = [breadcrumb[0], breadcrumb[1], heading_text]
                    else:
                        breadcrumb = [doc_title, heading_text]

                current_lines.append(line)
                continue

        current_lines.append(line)

    # Flush final chunk
    if current_lines:
        flush_chunk()

    # If no headers were found (e.g. flat file), create single chunk
    if not chunks and text.strip():
        meta = extract_metadata(text, doc_title, doc_title)
        chunks.append({
            "id": f"{source_file}#1",
            "source": source_file,
            "doc_title": doc_title,
            "doc_type": doc_type,
            "section_title": doc_title,
            "breadcrumb": doc_title,
            "content": text.strip(),
            "category": meta["category"],
            "event_ids": meta["event_ids"],
            "hex_codes": meta["hex_codes"],
            "config_codes": meta["config_codes"],
            "wer_buckets": meta["wer_buckets"],
            "processes": meta["processes"],
            "tokens": meta["tokens"],
            "length": len(text)
        })

    return chunks
