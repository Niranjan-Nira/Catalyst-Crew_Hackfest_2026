from pathlib import Path
import re
from typing import Dict, List, Any

from .scorecard import generate_scorecard_data


def _sanitize_value(value: Any) -> Any:
    """Redact common endpoint identifiers before they are written to a report."""
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r"(?i)(C:\\Users\\)[^\\\s]+", r"\1[REDACTED_USER]", value)
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]", value)
    value = re.sub(r"(?i)\\b(?:computername|hostname|user(name)?)\s*[:=]\s*[^,;\s]+", r"\g<0> [REDACTED]", value)
    return value


def _timeline_entries(diagnosis_results: Dict[str, Any]) -> List[Dict[str, str]]:
    entries = []
    for finding in diagnosis_results.get("tier1_anomalies", []) + diagnosis_results.get("tier2_possible_anomalies", []):
        timestamp = finding.get("timestamp") or finding.get("start_time") or finding.get("event_time")
        if timestamp:
            entries.append({
                "time": str(timestamp),
                "id": str(finding.get("id", "Finding")),
                "event": str(finding.get("title", "Detected finding")),
                "source": str(finding.get("source_file", "Diagnostic evidence"))
            })
    return sorted(entries, key=lambda item: item["time"])

class CaseReportBuilder:
    """
    Assembles the 4-tier Case Report, Scorecard, and Consolidated Case Table
    matching the exact standard in Sample Output-Anomaly and RCA result.pdf.
    """

    @staticmethod
    def build_markdown_report(
        device_name: str,
        diagnosis_results: Dict[str, Any],
        rca_results: Dict[str, Any],
        sanitize_report: bool = False,
        coverage: Dict[str, Any] | None = None,
        luna_solution: Dict[str, Any] | None = None
    ) -> str:
        if sanitize_report:
            diagnosis_results = _sanitize_value(diagnosis_results)
            rca_results = _sanitize_value(rca_results)
            device_name = _sanitize_value(device_name)

        tier1 = diagnosis_results.get("tier1_anomalies", [])
        tier2 = diagnosis_results.get("tier2_possible_anomalies", [])
        tier3 = rca_results.get("tier3_root_causes", [])
        tier4 = rca_results.get("tier4_possible_root_causes", [])

        lines = []
        lines.append(f"# Diagnostic & Root Cause Analysis Case Report: {device_name}\n")

        # Executive summary keeps the first page useful for incident triage.
        all_findings = tier1 + tier2
        severity = "Critical" if tier1 else ("Warning" if tier2 else "Informational")
        top_issue = (tier1 or tier2 or [{"title": "No significant anomaly detected"}])[0].get("title")
        top_action = (tier3 or tier4 or [{"recommended_action": "Continue monitoring and collect more telemetry."}])[0].get("recommended_action", "")
        lines.extend([
            "## Executive Summary",
            f"**Overall status:** {severity} | **Findings:** {len(all_findings)} | **Confirmed root causes:** {len(tier3)}",
            f"**Top issue:** {top_issue}",
            f"**First recommended action:** {top_action}",
            "Review the evidence and confidence level before applying any system change.\n",
        ])

        lines.append("## Timeline")
        timeline = _timeline_entries(diagnosis_results)
        if timeline:
            lines.extend(["| Time | Finding | Event | Source |", "|---|---|---|---|"])
            for item in timeline:
                lines.append(f"| {item['time']} | {item['id']} | {item['event']} | {item['source']} |")
        else:
            lines.append("No timestamped finding was available in the analyzed input.")
        lines.append("")

        lines.append("## Evidence Traceability")
        lines.extend(["| Finding | Evidence | Source |", "|---|---|---|"])
        for finding in all_findings:
            evidence = finding.get("evidence", []) or ["No detailed evidence recorded"]
            for evidence_item in evidence[:3]:
                lines.append(f"| {finding.get('id', 'Finding')} | {str(evidence_item).replace('|', '-')} | {finding.get('source_file', 'Not recorded')} |")
        lines.append("")

        # 1. ANOMALIES (Tier 1)
        lines.append("## 1. ANOMALIES (high confidence — clear, corroborated evidence)\n")
        for a in tier1:
            aid = a.get('id', 'A?')
            title = a.get('title', 'Anomaly')
            cat_text = a.get('category', '').replace('_', ' ').title()
            lines.append(f"### {aid}. {title}")
            lines.append(f"**Category:** {cat_text}")
            lines.append("**Evidence (ranked):**")
            for idx, ev in enumerate(a.get("evidence", []), 1):
                lines.append(f"{idx}. {ev}")
            lines.append(f"**Confidence:** {a.get('confidence', 80)}% ({a.get('confidence_reason', '')})")
            lines.append(f"**Source file:** `{a.get('source_file', '')}`\n")

        # 2. POSSIBLE ANOMALIES (Tier 2)
        lines.append("## 2. POSSIBLE ANOMALIES (moderate confidence — worth flagging, needs more data to confirm)\n")
        for b in tier2:
            bid = b.get('id', 'B?')
            title = b.get('title', 'Possible Anomaly')
            cat_text = b.get('category', '').replace('_', ' ').title()
            lines.append(f"### {bid}. {title}")
            lines.append(f"**Category:** {cat_text}")
            lines.append("**Evidence:**")
            for idx, ev in enumerate(b.get("evidence", []), 1):
                lines.append(f"- {ev}")
            lines.append(f"**Why 'possible' not confirmed:** {b.get('confidence_reason', '')}")
            lines.append(f"**Confidence:** {b.get('confidence', 50)}%")
            lines.append(f"**Source file:** `{b.get('source_file', '')}`\n")

        # 3. ROOT CAUSES (Tier 3)
        lines.append("## 3. ROOT CAUSES (evidence directly supports the explanation)\n")
        for c in tier3:
            cid = c.get('id', 'C?')
            title = c.get('title', 'Root Cause')
            lines.append(f"### {cid}. {title}")
            lines.append(f"**Root cause:** {c.get('root_cause', '')}")
            lines.append(f"**Recommended action:** {c.get('recommended_action', '')}")
            lines.append(f"**Confidence:** {c.get('confidence', 70)}% ({c.get('confidence_reason', '')})\n")

        # 4. POSSIBLE ROOT CAUSES (Tier 4)
        lines.append("## 4. POSSIBLE ROOT CAUSES (plausible, but not fully confirmed by available evidence)\n")
        for d in tier4:
            did = d.get('id', 'D?')
            title = d.get('title', 'Possible Root Cause')
            lines.append(f"### {did}. {title}")
            lines.append(f"**Hypothesis:** {d.get('hypothesis', '')}")
            lines.append(f"**Why 'possible' not confirmed:** {d.get('why_possible_not_confirmed', '')}")
            lines.append(f"**What would confirm it:** {d.get('what_would_confirm_it', '')}")
            lines.append(f"**Recommended action:** {d.get('recommended_action', '')}")
            lines.append(f"**Confidence:** {d.get('confidence', 50)}% ({d.get('confidence_reason', '')})\n")

        lines.append("## Recommended Actions")
        actions = tier3 + tier4
        if actions:
            for index, action in enumerate(actions, 1):
                confidence = action.get("confidence", 50)
                lines.append(f"{index}. **{action.get('recommended_action', 'Collect more evidence')}** (confidence: {confidence}%; review rollback options before execution)")
        else:
            lines.append("1. Continue monitoring and collect a longer telemetry window.")
        lines.append("")

        lines.append("## Privacy and Data Handling")
        if sanitize_report:
            lines.append("Sensitive endpoint identifiers were redacted in this report, including common user paths, IP addresses, and host/user labels.")
        else:
            lines.append("This report may contain usernames, computer names, file paths, IP addresses, process names, and hardware identifiers. Store and share it according to your organization’s data-handling policy.")
        lines.append("")

        lines.append("## Limitations")
        if coverage:
            lines.append(f"Input coverage: {coverage.get('detected', 0)}/{coverage.get('expected', 0)} expected diagnostic modules.")
            missing = coverage.get("missing", [])
            if missing:
                lines.append(f"Missing modules: {', '.join(missing)}")
        else:
            lines.append("Module coverage was not supplied by the caller.")
        lines.append("Findings depend on the quality, completeness, and timestamp consistency of the supplied telemetry; possible causes are not confirmed diagnoses.\n")

        if luna_solution and luna_solution.get("summary"):
            lines.append("## Luna 5.6 Solution Guide")
            lines.append("*Generated from the local case evidence because LUNA_ENABLED=1.*\n")
            lines.append(str(luna_solution["summary"]))
            lines.append("")

        # 5. SCORECARD
        lines.append("## 5. SCORECARD (matches the hackathon's required output shape)\n")
        lines.append("| # | Issue | Evidence (top signal) | Category | Confidence | Recommended Action |")
        lines.append("|---|---|---|---|---|---|")
        scorecard_rows = generate_scorecard_data(diagnosis_results, rca_results)
        for r in scorecard_rows:
            clean_issue = str(r.get("issue", "")).replace("|", "-")
            clean_ev = str(r.get("evidence_top_signal", "")).replace("|", "-").replace("\n", " ")
            clean_rec = str(r.get("recommended_action", "")).replace("|", "-").replace("\n", " ")
            lines.append(f"| **{r.get('id', '')}** | {clean_issue} | {clean_ev} | {r.get('category', '')} | {r.get('confidence', '')} | {clean_rec} |")
        lines.append("\n")

        # 6. CONSOLIDATED CASE TABLE
        lines.append("## 6. CONSOLIDATED CASE TABLE — Anomaly → Evidence → Root Cause → Remediation\n")
        lines.append("| # | Anomaly | Evidence | Root Cause | Recommended Remediation | Confidence |")
        lines.append("|---|---|---|---|---|---|")

        # Map C1/D1 to A1, etc.
        root_cause_map = {}
        for c in tier3:
            target_id = c.get("target_anomaly_id", c.get("id", ""))
            root_cause_map[target_id] = (c.get("root_cause", ""), c.get("recommended_action", ""), f"{c.get('confidence', 70)}%")
        for d in tier4:
            target_id = d.get("target_anomaly_id", d.get("id", ""))
            root_cause_map[target_id] = (f"{d.get('hypothesis', '')} *(unconfirmed)*", d.get("recommended_action", ""), f"{d.get('confidence', 50)}%")

        for a in tier1:
            aid = a.get("id", "A?")
            title = str(a.get("title", "")).replace("|", "-")
            ev_items = [str(e).replace("|", "-").replace("\n", " ") for e in a.get("evidence", [])]
            ev_str = "<br>".join(ev_items)
            rc_info = root_cause_map.get(aid, ("Under investigation", "Monitor system", f"{a.get('confidence', 80)}%"))
            lines.append(f"| **{aid}** | {title} | {ev_str} | {rc_info[0]} | {rc_info[1]} | {rc_info[2]} |")

        for b in tier2:
            bid = b.get("id", "B?")
            title = str(b.get("title", "")).replace("|", "-")
            ev_items = [str(e).replace("|", "-").replace("\n", " ") for e in b.get("evidence", [])]
            ev_str = "<br>".join(ev_items)
            rc_info = root_cause_map.get(bid, ("Pending longer telemetry window", "Extend observation window", f"{b.get('confidence', 50)}%"))
            lines.append(f"| **{bid}** | {title} | {ev_str} | {rc_info[0]} | {rc_info[1]} | {rc_info[2]} |")

        lines.append("\n---\n*Report generated by Endpoint AI Workstation Diagnostic Agent.*")
        report = "\n".join(lines)
        return _sanitize_value(report) if sanitize_report else report
