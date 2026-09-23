from pathlib import Path
import re
from datetime import datetime, timezone
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


def _default_report_metadata(
    device_name: str,
    diagnosis_results: Dict[str, Any],
    coverage: Dict[str, Any] | None,
    sanitize_report: bool,
) -> Dict[str, Any]:
    tier1 = diagnosis_results.get("tier1_anomalies", [])
    tier2 = diagnosis_results.get("tier2_possible_anomalies", [])
    expected = coverage.get("expected", 0) if coverage else 0
    detected = coverage.get("detected", 0) if coverage else 0
    return {
        "incident_id": f"INC-{str(device_name).replace(' ', '_')}",
        "target_workstation": device_name,
        "report_generated_at": datetime.now(timezone.utc).isoformat(),
        "report_version": "1.3.0",
        "severity": "CRITICAL" if tier1 else ("WARNING" if tier2 else "INFORMATIONAL"),
        "sanitized": sanitize_report,
        "evidence_coverage": f"{detected}/{expected}" if expected else "Not supplied",
    }


def _default_impact_summary(
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any],
) -> List[str]:
    summary = []
    for finding in diagnosis_results.get("tier1_anomalies", []):
        title = str(finding.get("title", "")).lower()
        if "crash cluster" in title:
            count = finding.get("distinct_process_count")
            duration = finding.get("duration_seconds")
            detail = f"{count} processes crashed" if count else "Multiple processes crashed"
            if duration:
                detail += f" within {duration} seconds"
            summary.append(detail + ".")
        elif "graphics" in title or "display" in title:
            count = finding.get("raw_count")
            summary.append(f"Graphics/display stability was affected{f' ({count} recorded events)' if count else ''}.")
        elif "hardware device" in title or "ethernet" in title or "driver" in title:
            summary.append("A hardware device or driver initialization issue was detected.")
    if not summary and rca_results.get("tier3_root_causes"):
        summary.append("Confirmed root-cause candidates require remediation and verification.")
    if not summary:
        summary.append("No direct user-impact signal was recorded in the analyzed evidence.")
    return list(dict.fromkeys(summary))


def _action_owner(action: Dict[str, Any]) -> str:
    text = f"{action.get('title', '')} {action.get('recommended_action', '')}".lower()
    if any(term in text for term in ("office", "powerpoint", "onedrive")):
        return "Desktop Support"
    if any(term in text for term in ("memory", "ssd", "disk", "storage")):
        return "Endpoint Engineering"
    if any(term in text for term in ("ethernet", "nic", "driver", "graphics", "gpu", "display")):
        return "Endpoint Engineering"
    return "Incident Response Team"


def _action_rollback(action: Dict[str, Any]) -> str:
    text = f"{action.get('title', '')} {action.get('recommended_action', '')}".lower()
    if any(term in text for term in ("driver", "graphics", "ethernet", "nic")):
        return "Restore the previous known-good driver and reboot if the change causes regression."
    if any(term in text for term in ("office", "powerpoint", "onedrive")):
        return "Restore the previous application version or uninstall the update if stability worsens."
    if "spektion" in text or "sensor" in text:
        return "Reinstall the last known-good sensor build and re-enable the prior policy configuration."
    return "Stop the change, preserve the evidence, and return to the last known-good configuration."


def _action_verification(action: Dict[str, Any]) -> str:
    text = f"{action.get('title', '')} {action.get('recommended_action', '')}".lower()
    if action.get("what_would_confirm_it"):
        return str(action["what_would_confirm_it"])
    if "crash cluster" in text or "spektion" in text:
        return "Collect 48 hours of telemetry with no repeat multi-process crash cluster."
    if "office" in text or "powerpoint" in text:
        return "Open, edit, and save a PowerPoint test file without a repeat WER crash."
    if "ethernet" in text or "nic" in text:
        return "Confirm the device has no active ConfigManager error and passes network connectivity checks."
    if "graphics" in text or "display" in text or "gpu" in text:
        return "Compare the next telemetry window and confirm the related display errors do not recur."
    if "memory" in text:
        return "Capture memory during active use and confirm available memory remains above the investigation threshold."
    return "Re-run the relevant diagnostic module and confirm the finding is resolved or reduced."


def _build_action_items(
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    items = []
    actions = []
    for cause in rca_results.get("tier3_root_causes", []):
        actions.append((cause, "Confirmed root cause"))
    for hypothesis in rca_results.get("tier4_possible_root_causes", []):
        actions.append((hypothesis, "Possible root cause"))
    for index, (action, category) in enumerate(actions, 1):
        confidence = int(action.get("confidence", 50))
        items.append({
            "id": f"ACT-{index:03d}",
            "finding_ids": [action.get("target_anomaly_id", action.get("id", "Finding"))],
            "action": action.get("recommended_action", "Collect more evidence"),
            "priority": "P1" if category == "Confirmed root cause" and confidence >= 70 else ("P2" if confidence >= 50 else "P3"),
            "owner": _action_owner(action),
            "status": "Open",
            "rollback": _action_rollback(action),
            "verification": _action_verification(action),
            "confidence": f"{confidence}%",
        })
    if not items:
        items.append({
            "id": "ACT-001",
            "finding_ids": [],
            "action": "Continue monitoring and collect a longer telemetry window.",
            "priority": "P3",
            "owner": "Incident Response Team",
            "status": "Open",
            "rollback": "No system change is planned.",
            "verification": "Review the next telemetry window for newly confirmed findings.",
            "confidence": "N/A",
        })
    return items


def _build_siem_action_records(action_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records = []
    for item in action_items:
        records.append({
            "action_id": item["id"],
            "finding_ids": item["finding_ids"],
            "priority": item["priority"],
            "short_description": str(item["action"])[:160],
            "description": item["action"],
            "assignment_group": item["owner"],
            "state": item["status"],
            "rollback_plan": item["rollback"],
            "verification_plan": item["verification"],
            "confidence": item["confidence"],
            "work_notes": "Generated from evidence-backed endpoint diagnosis; review before execution.",
        })
    return records


def _build_report_chart_data(
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    findings = diagnosis_results.get("tier1_anomalies", []) + diagnosis_results.get("tier2_possible_anomalies", [])
    crash_timeline = []
    for finding in findings:
        timestamp = finding.get("start_time") or finding.get("timestamp") or finding.get("event_time")
        if timestamp:
            crash_timeline.append({
                "label": str(timestamp)[:16],
                "value": finding.get("distinct_process_count", finding.get("raw_count", 1)),
                "finding_id": finding.get("id", "Finding"),
            })

    event_frequency = [
        {"label": finding.get("id", "Finding"), "value": finding.get("raw_count"), "title": finding.get("title", "")}
        for finding in findings
        if isinstance(finding.get("raw_count"), (int, float)) and finding.get("raw_count", 0) > 0
    ]
    event_frequency.sort(key=lambda item: item["value"], reverse=True)

    memory_pressure = [
        {"label": finding.get("id", "Finding"), "value": finding.get("min_available_mb"), "title": finding.get("title", "")}
        for finding in findings
        if isinstance(finding.get("min_available_mb"), (int, float))
    ]

    confidence = []
    for finding in findings:
        if isinstance(finding.get("confidence"), (int, float)):
            confidence.append({"label": finding.get("id", "Finding"), "value": finding["confidence"]})
    for cause in rca_results.get("tier3_root_causes", []) + rca_results.get("tier4_possible_root_causes", []):
        if isinstance(cause.get("confidence"), (int, float)):
            confidence.append({"label": cause.get("id", "RCA"), "value": cause["confidence"]})

    return {
        "crash_timeline": crash_timeline[:12],
        "event_frequency": event_frequency[:12],
        "memory_pressure": memory_pressure[:12],
        "confidence": confidence[:20],
    }


def _build_finding_root_cause_map(
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    causes = {}
    for cause in rca_results.get("tier3_root_causes", []) + rca_results.get("tier4_possible_root_causes", []):
        target_id = cause.get("target_anomaly_id", cause.get("id", ""))
        causes.setdefault(target_id, []).append(cause)

    rows = []
    findings = diagnosis_results.get("tier1_anomalies", []) + diagnosis_results.get("tier2_possible_anomalies", [])
    for finding in findings:
        finding_id = finding.get("id", "Finding")
        related = causes.get(finding_id, [])
        if related:
            for cause in related:
                is_confirmed = cause in rca_results.get("tier3_root_causes", [])
                rows.append({
                    "finding_id": finding_id,
                    "finding": finding.get("title", "Detected finding"),
                    "root_cause_id": cause.get("id", "RCA"),
                    "root_cause": cause.get("root_cause", cause.get("hypothesis", "")),
                    "relationship": "Supported explanation" if is_confirmed else "Unconfirmed hypothesis",
                    "confidence": f"{cause.get('confidence', 50)}%",
                })
        else:
            rows.append({
                "finding_id": finding_id,
                "finding": finding.get("title", "Detected finding"),
                "root_cause_id": "Pending",
                "root_cause": "No root cause is currently linked to this finding.",
                "relationship": "Investigation pending",
                "confidence": "N/A",
            })
    return rows


def _build_evidence_quality(
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any],
    coverage: Dict[str, Any] | None,
) -> Dict[str, Any]:
    findings = diagnosis_results.get("tier1_anomalies", []) + diagnosis_results.get("tier2_possible_anomalies", [])
    evidenced = [finding for finding in findings if finding.get("evidence")]
    sources = {finding.get("source_file") for finding in evidenced if finding.get("source_file")}
    expected = coverage.get("expected", 0) if coverage else 0
    detected = coverage.get("detected", 0) if coverage else 0
    coverage_complete = bool(expected and detected >= expected)
    evidence_ratio = len(evidenced) / len(findings) if findings else 0
    quality = "High" if coverage_complete and evidence_ratio >= 0.8 else ("Medium" if evidence_ratio >= 0.5 else "Low")
    missing = list(coverage.get("missing", [])) if coverage else []
    unresolved = []
    for hypothesis in rca_results.get("tier4_possible_root_causes", []):
        confirmation = hypothesis.get("what_would_confirm_it")
        if confirmation:
            unresolved.append(str(confirmation))
    return {
        "quality": quality,
        "findings_with_evidence": len(evidenced),
        "total_findings": len(findings),
        "source_count": len(sources),
        "coverage": f"{detected}/{expected}" if expected else "Not supplied",
        "missing_modules": missing,
        "unresolved_artifacts": unresolved,
    }

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
        luna_solution: Dict[str, Any] | None = None,
        report_metadata: Dict[str, Any] | None = None,
        impact_summary: List[str] | None = None
    ) -> str:
        if sanitize_report:
            diagnosis_results = _sanitize_value(diagnosis_results)
            rca_results = _sanitize_value(rca_results)
            device_name = _sanitize_value(device_name)

        tier1 = diagnosis_results.get("tier1_anomalies", [])
        tier2 = diagnosis_results.get("tier2_possible_anomalies", [])
        tier3 = rca_results.get("tier3_root_causes", [])
        tier4 = rca_results.get("tier4_possible_root_causes", [])
        action_items = _build_action_items(diagnosis_results, rca_results)
        finding_root_causes = _build_finding_root_cause_map(diagnosis_results, rca_results)
        evidence_quality = _build_evidence_quality(diagnosis_results, rca_results, coverage)
        chart_data = _build_report_chart_data(diagnosis_results, rca_results)
        report_metadata = report_metadata or _default_report_metadata(
            device_name, diagnosis_results, coverage, sanitize_report
        )
        impact_summary = impact_summary or _default_impact_summary(diagnosis_results, rca_results)

        lines = []
        lines.append(f"# Diagnostic & Root Cause Analysis Case Report: {device_name}\n")

        lines.extend([
            "## Incident Metadata",
            f"**Incident ID:** {report_metadata.get('incident_id', 'Not recorded')}",
            f"**Target workstation:** {report_metadata.get('target_workstation', device_name)}",
            f"**Report generated:** {report_metadata.get('report_generated_at', 'Not recorded')}",
            f"**Report version:** {report_metadata.get('report_version', 'Not recorded')}",
            f"**Severity:** {report_metadata.get('severity', 'Not recorded')}",
            f"**Evidence coverage:** {report_metadata.get('evidence_coverage', 'Not supplied')}",
            f"**Sensitive identifiers sanitized:** {'Yes' if report_metadata.get('sanitized', sanitize_report) else 'No'}\n",
            "## Impact Summary",
        ])
        lines.extend(f"- {impact}" for impact in impact_summary)
        lines.append("")

        lines.append("## Diagnostic Charts")
        chart_specs = [
            ("Crash Timeline", "crash_timeline", "Count"),
            ("Event Frequency", "event_frequency", "Events"),
            ("Memory Pressure", "memory_pressure", "Minimum available MB"),
            ("Confidence Distribution", "confidence", "Percent"),
        ]
        for chart_title, chart_key, value_label in chart_specs:
            lines.append(f"### {chart_title}")
            lines.append(f"| Signal | {value_label} | Relative |")
            lines.append("|---|---:|---|")
            chart_items = chart_data[chart_key]
            if not chart_items:
                lines.append("| No data available | - | - |")
                lines.append("")
                continue
            maximum = max(float(item["value"]) for item in chart_items) or 1
            for item in chart_items:
                relative = round(float(item["value"]) / maximum * 100)
                lines.append(f"| {item['label']} | {item['value']} | {relative}% |")
            lines.append("")

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
            for evidence_item in evidence:
                lines.append(f"| {finding.get('id', 'Finding')} | {str(evidence_item).replace('|', '-')} | {finding.get('source_file', 'Not recorded')} |")
        lines.append("")

        lines.append("## Finding to Root-Cause Mapping")
        lines.extend([
            "| Finding | Root Cause | Relationship | Confidence |",
            "|---|---|---|---|",
        ])
        for row in finding_root_causes:
            lines.append(
                f"| {row['finding_id']}: {str(row['finding']).replace('|', '-')} | "
                f"{row['root_cause_id']}: {str(row['root_cause']).replace('|', '-')} | "
                f"{row['relationship']} | {row['confidence']} |"
            )
        lines.append("")

        lines.append("## Evidence Quality and Missing Artifacts")
        lines.append(
            f"**Quality:** {evidence_quality['quality']} | **Findings with evidence:** "
            f"{evidence_quality['findings_with_evidence']}/{evidence_quality['total_findings']} | "
            f"**Distinct source files:** {evidence_quality['source_count']} | "
            f"**Module coverage:** {evidence_quality['coverage']}"
        )
        if evidence_quality["missing_modules"]:
            lines.append(f"**Missing modules:** {', '.join(evidence_quality['missing_modules'])}")
        if evidence_quality["unresolved_artifacts"]:
            lines.append("**Unresolved artifacts needed for confirmation:**")
            lines.extend(f"- {artifact}" for artifact in evidence_quality["unresolved_artifacts"])
        if not evidence_quality["missing_modules"] and not evidence_quality["unresolved_artifacts"]:
            lines.append("No missing modules or explicitly requested confirmation artifacts were recorded.")
        lines.append("")

        # 1. ANOMALIES (Tier 1)
        lines.append("## 1. ANOMALIES (high confidence — clear, corroborated evidence)\n")
        for a in tier1:
            aid = a.get('id', 'A?')
            title = a.get('title', 'Anomaly')
            cat_text = a.get('category', '').replace('_', ' ').title()
            lines.append(f"### {aid}. {title}")
            lines.append(f"**Category:** {cat_text}")
            evidence = a.get("evidence", []) or ["No detailed evidence recorded"]
            lines.append(f"**Top evidence signal:** {evidence[0]}")
            lines.append(f"See the Evidence Traceability table for the complete {len(evidence)}-item evidence chain.")
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
            evidence = b.get("evidence", []) or ["No detailed evidence recorded"]
            lines.append(f"**Top evidence signal:** {evidence[0]}")
            lines.append(f"See the Evidence Traceability table for the complete {len(evidence)}-item evidence chain.")
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

        lines.append("## Prioritized Action Plan")
        lines.extend([
            "| ID | Finding | Priority | Action | Owner | Status | Rollback | Verification |",
            "|---|---|---|---|---|---|---|---|",
        ])
        for item in action_items:
            values = [
                item["id"], ", ".join(item["finding_ids"]), item["priority"], item["action"],
                item["owner"], item["status"], item["rollback"], item["verification"],
            ]
            lines.append("| " + " | ".join(str(value).replace("|", "-").replace("\n", " ") for value in values) + " |")
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
            evidence_count = len(a.get("evidence", []))
            ev_str = f"See Evidence Traceability ({aid}; {evidence_count} evidence items)"
            rc_info = root_cause_map.get(aid, ("Under investigation", "Monitor system", f"{a.get('confidence', 80)}%"))
            lines.append(f"| **{aid}** | {title} | {ev_str} | {rc_info[0]} | {rc_info[1]} | {rc_info[2]} |")

        for b in tier2:
            bid = b.get("id", "B?")
            title = str(b.get("title", "")).replace("|", "-")
            evidence_count = len(b.get("evidence", []))
            ev_str = f"See Evidence Traceability ({bid}; {evidence_count} evidence items)"
            rc_info = root_cause_map.get(bid, ("Pending longer telemetry window", "Extend observation window", f"{b.get('confidence', 50)}%"))
            lines.append(f"| **{bid}** | {title} | {ev_str} | {rc_info[0]} | {rc_info[1]} | {rc_info[2]} |")

        lines.append("\n---\n*Report generated by Endpoint AI Workstation Diagnostic Agent.*")
        report = "\n".join(lines)
        return _sanitize_value(report) if sanitize_report else report
