import re
from typing import Dict, Optional


def build_local_solution_from_rca(
    diag_results: Dict,
    rca_results: Dict,
    issue_details: Optional[str] = None,
) -> Dict:
    """Build the offline solution brief used by the Community tab."""
    tier3 = rca_results.get("tier3_root_causes", [])
    tier4 = rca_results.get("tier4_possible_root_causes", [])
    tier1 = {item.get("id"): item for item in diag_results.get("tier1_anomalies", [])}
    tier2 = {item.get("id"): item for item in diag_results.get("tier2_possible_anomalies", [])}

    if not tier3 and not tier4:
        return {
            "summary": (
                "### Local solution brief\n\n"
                "No high-confidence root cause is available yet. Review the Findings tab, "
                "collect more telemetry, and rerun the analysis."
            ),
            "model_used": "Local RCA fallback",
            "is_online": False,
            "thread_count": 0,
            "source": "Local diagnosis and RCA",
        }

    primary = tier3[0] if tier3 else tier4[0]
    target_id = primary.get("target_anomaly_id", "")
    target = tier1.get(target_id) or tier2.get(target_id) or {}
    lines = [
        "### Local solution brief",
        "",
        f"**Main issue:** {target.get('title', primary.get('title', 'Detected endpoint issue'))}",
        f"**Confidence:** {primary.get('confidence', target.get('confidence', 'N/A'))}%",
        "",
        "#### What the evidence says",
        primary.get("root_cause") or primary.get("hypothesis", "The issue needs more evidence."),
        "",
        "#### Recommended resolution",
        f"1. {primary.get('recommended_action', 'Collect more evidence before making a system change.')}",
    ]

    for cause in tier3[1:3]:
        lines.extend([
            "",
            f"#### Additional finding: {cause.get('title', cause.get('id', 'RCA'))}",
            cause.get("root_cause", ""),
            f"**Action:** {cause.get('recommended_action', '')}",
        ])

    if tier4:
        lines.extend(["", "#### What to verify next"])
        for hypothesis in tier4[:3]:
            lines.append(
                f"- {hypothesis.get('what_would_confirm_it', hypothesis.get('recommended_action', 'Continue monitoring.'))}"
            )

    lines.extend([
        "",
        "#### Safety note",
        "Apply remediation only after reviewing the evidence. Use the Actions tab's PowerShell `-WhatIf` mode before making changes.",
        "",
        f"**Source:** Local diagnosis, ranked evidence, and RAG citations. {issue_details or ''}",
    ])
    return {
        "summary": "\n".join(lines),
        "model_used": "Local RCA fallback",
        "is_online": False,
        "thread_count": 0,
        "source": "Local diagnosis and RCA",
    }


def _clean_issue_title_for_query(title: str) -> str:
    cleaned = re.sub(
        r"^(RCA\s+for\s+[A-Z0-9_\-]+\s*(\([^)]*\))?\s*[—\-–:]?\s*|[A-Z0-9_\-]+\.\s*)",
        "",
        title,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.replace("—", " ").replace("–", " ").replace("-", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_primary_issue(diag_results: dict, rca_results: dict) -> Dict:
    """Build local issue selector data without any Reddit dependency."""
    candidates = []

    for cause in rca_results.get("tier3_root_causes", []):
        title = cause.get("title", "")
        clean_title = _clean_issue_title_for_query(title)
        candidates.append({
            "id": cause.get("id", "T3"),
            "tier": "Tier-3 Root Cause",
            "title": title,
            "clean_title": clean_title,
            "root_cause": cause.get("root_cause", ""),
            "action": cause.get("recommended_action", ""),
            "confidence": cause.get("confidence", 85),
            "suggested_query": f"How to solve {clean_title}",
        })

    for anomaly in diag_results.get("tier1_anomalies", []):
        title = anomaly.get("title", "")
        clean_title = _clean_issue_title_for_query(title)
        candidates.append({
            "id": str(anomaly.get("id", "T1")),
            "tier": "Tier-1 Anomaly",
            "title": title,
            "clean_title": clean_title,
            "root_cause": anomaly.get("confidence_reason", ""),
            "action": (anomaly.get("evidence") or [""])[0],
            "confidence": anomaly.get("confidence", 90),
            "suggested_query": f"How to solve {clean_title}",
        })

    for hypothesis in rca_results.get("tier4_possible_root_causes", []):
        title = hypothesis.get("title", "")
        clean_title = _clean_issue_title_for_query(title)
        candidates.append({
            "id": hypothesis.get("id", "T4"),
            "tier": "Tier-4 Hypothesis",
            "title": title,
            "clean_title": clean_title,
            "root_cause": hypothesis.get("hypothesis", ""),
            "action": hypothesis.get("recommended_action", ""),
            "confidence": hypothesis.get("confidence", 60),
            "suggested_query": f"How to solve {clean_title}",
        })

    if not candidates:
        return {
            "primary_id": "DEFAULT",
            "primary_title": "Generic System Diagnostics",
            "query": "How to solve Windows application crash 0xC0000005",
            "details": "No specific critical anomalies detected in diagnostic payload.",
            "candidates": [],
        }

    primary = candidates[0]
    query = primary["suggested_query"]
    lowered = primary["title"].lower()
    if "0xc0000005" in lowered:
        query = "How to solve application crash error 0xC0000005"
    elif "powerpoint" in lowered:
        query = "How to solve PowerPoint crash"
    elif "ethernet" in lowered or "i219" in lowered:
        query = "How to solve Intel Ethernet device startup failure"

    return {
        "primary_id": primary["id"],
        "primary_title": primary["title"],
        "query": query,
        "details": primary["root_cause"] or primary["action"],
        "candidates": candidates,
    }
