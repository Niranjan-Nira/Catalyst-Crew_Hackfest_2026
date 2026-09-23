import html
from pathlib import Path
from typing import Dict, List, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String
from .scorecard import generate_scorecard_data
from .report_builder import (
    _default_impact_summary,
    _default_report_metadata,
    _build_action_items,
    _build_evidence_quality,
    _build_finding_root_cause_map,
    _build_report_chart_data,
    _sanitize_value,
    _timeline_entries,
)

def _esc(val: Any) -> str:
    """Escapes strings for ReportLab XML flowables, preventing XML parse crashes."""
    if val is None:
        return ""
    return html.escape(str(val))


def _bar_chart(title: str, items: List[Dict[str, Any]], color: colors.Color) -> Drawing:
    """Create a compact horizontal bar chart that remains readable in a PDF."""
    visible_items = items[:10]
    row_height = 18
    chart = Drawing(520, 34 + row_height * max(1, len(visible_items)))
    chart.add(String(0, chart.height - 14, title, fontName="Helvetica-Bold", fontSize=9))
    if not visible_items:
        chart.add(String(0, chart.height - 31, "No data available", fontName="Helvetica", fontSize=7, fillColor=colors.grey))
        return chart
    maximum = max(float(item["value"]) for item in visible_items) or 1
    bar_x = 145
    bar_width = 300
    for index, item in enumerate(visible_items):
        y = chart.height - 32 - (index + 1) * row_height
        label = str(item.get("label", ""))[:22]
        value = float(item.get("value", 0))
        chart.add(String(0, y + 4, label, fontName="Helvetica", fontSize=7))
        chart.add(Rect(bar_x, y + 2, max(2, bar_width * value / maximum), 10, fillColor=color, strokeColor=None))
        display_value = f"{value:.0f}" if value.is_integer() else f"{value:.1f}"
        chart.add(String(bar_x + bar_width + 8, y + 4, display_value, fontName="Helvetica", fontSize=7))
    return chart


class PDFReportGenerator:
    """
    Generates a pixel-perfect, printable PDF report that faithfully reproduces
    the layout, typography, scorecard, and consolidated case table of
    Sample Output-Anomaly and RCA result.pdf.
    """

    @staticmethod
    def generate_pdf(
        output_path: Path,
        diagnosis_results: Dict[str, Any],
        rca_results: Dict[str, Any],
        title_text: str = "Sample Anomaly and RCA",
        sanitize_report: bool = False,
        coverage: Dict[str, Any] | None = None,
        luna_solution: Dict[str, Any] | None = None,
        report_metadata: Dict[str, Any] | None = None,
        impact_summary: List[str] | None = None,
        target_workstation: str | None = None
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        # Custom Styles matching reference PDF
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.black,
            spaceAfter=14
        )

        section_heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.black,
            spaceBefore=10,
            spaceAfter=8
        )

        item_title_style = ParagraphStyle(
            "ItemTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.black,
            spaceBefore=6,
            spaceAfter=3
        )

        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.black,
            spaceAfter=3
        )

        body_bold_style = ParagraphStyle(
            "BodyBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.black,
            spaceAfter=3
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.black
        )

        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.black
        )

        table_cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.black
        )

        story = []

        # Document Header
        story.append(Paragraph(title_text, title_style))
        story.append(HRFlowable(width="100%", thickness=0.75, color=colors.gray, spaceAfter=12, spaceBefore=4))

        if sanitize_report:
            diagnosis_results = _sanitize_value(diagnosis_results)
            rca_results = _sanitize_value(rca_results)

        tier1 = diagnosis_results.get("tier1_anomalies", [])
        tier2 = diagnosis_results.get("tier2_possible_anomalies", [])
        tier3 = rca_results.get("tier3_root_causes", [])
        tier4 = rca_results.get("tier4_possible_root_causes", [])
        action_items = _build_action_items(diagnosis_results, rca_results)
        finding_root_causes = _build_finding_root_cause_map(diagnosis_results, rca_results)
        evidence_quality = _build_evidence_quality(diagnosis_results, rca_results, coverage)
        chart_data = _build_report_chart_data(diagnosis_results, rca_results)
        report_metadata = report_metadata or _default_report_metadata(
            target_workstation or title_text, diagnosis_results, coverage, sanitize_report
        )
        impact_summary = impact_summary or _default_impact_summary(diagnosis_results, rca_results)

        story.append(Paragraph("Incident Metadata", section_heading_style))
        metadata_rows = [
            [Paragraph("Incident ID", table_header_style), Paragraph(_esc(report_metadata.get("incident_id", "Not recorded")), table_cell_style)],
            [Paragraph("Target workstation", table_header_style), Paragraph(_esc(report_metadata.get("target_workstation", "Not recorded")), table_cell_style)],
            [Paragraph("Report generated", table_header_style), Paragraph(_esc(report_metadata.get("report_generated_at", "Not recorded")), table_cell_style)],
            [Paragraph("Report version", table_header_style), Paragraph(_esc(report_metadata.get("report_version", "Not recorded")), table_cell_style)],
            [Paragraph("Severity", table_header_style), Paragraph(_esc(report_metadata.get("severity", "Not recorded")), table_cell_style)],
            [Paragraph("Evidence coverage", table_header_style), Paragraph(_esc(report_metadata.get("evidence_coverage", "Not supplied")), table_cell_style)],
            [Paragraph("Identifiers sanitized", table_header_style), Paragraph("Yes" if report_metadata.get("sanitized", sanitize_report) else "No", table_cell_style)],
        ]
        metadata_table = Table(metadata_rows, colWidths=[125, 395])
        metadata_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(metadata_table)
        story.append(Paragraph("Impact Summary", section_heading_style))
        for impact in impact_summary:
            story.append(Paragraph(f"• {_esc(impact)}", body_style))

        story.append(Paragraph("Diagnostic Charts", section_heading_style))
        story.append(_bar_chart("Crash Timeline", chart_data["crash_timeline"], colors.HexColor("#2563eb")))
        story.append(_bar_chart("Event Frequency", chart_data["event_frequency"], colors.HexColor("#0f766e")))
        story.append(_bar_chart("Memory Pressure (minimum available MB)", chart_data["memory_pressure"], colors.HexColor("#d97706")))
        story.append(_bar_chart("Confidence Distribution", chart_data["confidence"], colors.HexColor("#7c3aed")))

        # Executive summary and triage context appear before the detailed findings.
        severity = "Critical" if tier1 else ("Warning" if tier2 else "Informational")
        top_finding = (tier1 or tier2 or [{"title": "No significant anomaly detected"}])[0]
        top_action = (tier3 or tier4 or [{"recommended_action": "Continue monitoring and collect more telemetry."}])[0]
        story.append(Paragraph("Executive Summary", section_heading_style))
        story.append(Paragraph(
            f"<b>Overall status:</b> {_esc(severity)} &nbsp;&nbsp; "
            f"<b>Findings:</b> {len(tier1) + len(tier2)} &nbsp;&nbsp; "
            f"<b>Confirmed root causes:</b> {len(tier3)}", body_style))
        story.append(Paragraph(f"<b>Top issue:</b> {_esc(top_finding.get('title', ''))}", body_style))
        story.append(Paragraph(f"<b>First recommended action:</b> {_esc(top_action.get('recommended_action', ''))}", body_style))

        story.append(Paragraph("Timeline", section_heading_style))
        timeline_rows = [[Paragraph("Time", table_header_style), Paragraph("Finding", table_header_style), Paragraph("Event", table_header_style), Paragraph("Source", table_header_style)]]
        for item in _timeline_entries(diagnosis_results):
            timeline_rows.append([Paragraph(_esc(item["time"]), table_cell_style), Paragraph(_esc(item["id"]), table_cell_bold), Paragraph(_esc(item["event"]), table_cell_style), Paragraph(_esc(item["source"]), table_cell_style)])
        if len(timeline_rows) == 1:
            timeline_rows.append([Paragraph("No timestamped finding", table_cell_style), Paragraph("", table_cell_style), Paragraph("available", table_cell_style), Paragraph("", table_cell_style)])
        timeline_table = Table(timeline_rows, colWidths=[75, 45, 260, 105])
        timeline_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        story.append(timeline_table)

        story.append(Paragraph("Evidence Traceability", section_heading_style))
        evidence_rows = [[Paragraph("Finding", table_header_style), Paragraph("Evidence", table_header_style), Paragraph("Source", table_header_style)]]
        for finding in tier1 + tier2:
            for evidence in (finding.get("evidence", []) or ["No detailed evidence recorded"]):
                evidence_rows.append([Paragraph(_esc(finding.get("id", "Finding")), table_cell_bold), Paragraph(_esc(evidence), table_cell_style), Paragraph(_esc(finding.get("source_file", "Not recorded")), table_cell_style)])
        evidence_table = Table(evidence_rows, colWidths=[45, 335, 105])
        evidence_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        story.append(evidence_table)

        story.append(Paragraph("Finding to Root-Cause Mapping", section_heading_style))
        mapping_rows = [[
            Paragraph("Finding", table_header_style),
            Paragraph("Root Cause", table_header_style),
            Paragraph("Relationship", table_header_style),
            Paragraph("Confidence", table_header_style),
        ]]
        for row in finding_root_causes:
            mapping_rows.append([
                Paragraph(_esc(f"{row['finding_id']}: {row['finding']}"), table_cell_style),
                Paragraph(_esc(f"{row['root_cause_id']}: {row['root_cause']}"), table_cell_style),
                Paragraph(_esc(row["relationship"]), table_cell_style),
                Paragraph(_esc(row["confidence"]), table_cell_style),
            ])
        mapping_table = Table(mapping_rows, colWidths=[130, 230, 105, 55], repeatRows=1)
        mapping_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        story.append(mapping_table)

        story.append(Paragraph("Evidence Quality and Missing Artifacts", section_heading_style))
        story.append(Paragraph(
            f"<b>Quality:</b> {_esc(evidence_quality['quality'])} &nbsp;&nbsp; "
            f"<b>Findings with evidence:</b> {evidence_quality['findings_with_evidence']}/{evidence_quality['total_findings']} &nbsp;&nbsp; "
            f"<b>Distinct source files:</b> {evidence_quality['source_count']} &nbsp;&nbsp; "
            f"<b>Module coverage:</b> {_esc(evidence_quality['coverage'])}",
            body_style,
        ))
        for missing in evidence_quality["missing_modules"]:
            story.append(Paragraph(f"<b>Missing module:</b> {_esc(missing)}", body_style))
        for artifact in evidence_quality["unresolved_artifacts"]:
            story.append(Paragraph(f"<b>Confirmation artifact needed:</b> {_esc(artifact)}", body_style))
        if not evidence_quality["missing_modules"] and not evidence_quality["unresolved_artifacts"]:
            story.append(Paragraph("No missing modules or explicitly requested confirmation artifacts were recorded.", body_style))

        story.append(Paragraph("Privacy and Limitations", section_heading_style))
        privacy_text = "Sensitive endpoint identifiers were redacted in this report." if sanitize_report else "This report may contain usernames, computer names, file paths, IP addresses, process names, and hardware identifiers. Handle it according to organizational policy."
        coverage_text = ""
        if coverage:
            coverage_text = f" Input coverage: {coverage.get('detected', 0)}/{coverage.get('expected', 0)} modules."
            if coverage.get("missing"):
                coverage_text += f" Missing: {', '.join(coverage['missing'])}."
        story.append(Paragraph(_esc(privacy_text + coverage_text + " Findings depend on the completeness and timestamp consistency of the supplied telemetry; possible causes are not confirmed diagnoses."), body_style))

        if luna_solution and luna_solution.get("summary"):
            story.append(Paragraph("Luna 5.6 Solution Guide", section_heading_style))
            story.append(Paragraph("Generated from local case evidence because LUNA_ENABLED=1.", body_style))
            for paragraph in str(luna_solution["summary"]).split("\n"):
                if paragraph.strip():
                    story.append(Paragraph(_esc(paragraph), body_style))

        # ----------------------------------------------------
        # 1. ANOMALIES (High Confidence)
        # ----------------------------------------------------
        story.append(Paragraph("1. ANOMALIES (high confidence — clear, corroborated evidence)", section_heading_style))

        for a in tier1:
            aid = _esc(a.get('id', 'A?'))
            title = _esc(a.get('title', 'Anomaly'))
            story.append(Paragraph(f"<b>{aid}. {title}</b>", item_title_style))
            cat_text = _esc(a.get("category", "").replace("_", " ").title())
            evidence = a.get("evidence", []) or ["No detailed evidence recorded"]
            story.append(Paragraph(f"<b>Category:</b> {cat_text}", body_style))
            story.append(Paragraph(f"<b>Top evidence signal:</b> {_esc(evidence[0])}", body_style))
            story.append(Paragraph(f"See Evidence Traceability for the complete {len(evidence)}-item evidence chain.", body_style))
            story.append(Spacer(1, 4))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=8, spaceBefore=6))

        # ----------------------------------------------------
        # 2. POSSIBLE ANOMALIES (Moderate Confidence)
        # ----------------------------------------------------
        story.append(Paragraph("2. POSSIBLE ANOMALIES (moderate confidence — worth flagging, needs more data to confirm)", section_heading_style))

        for b in tier2:
            bid = _esc(b.get('id', 'B?'))
            title = _esc(b.get('title', 'Possible Anomaly'))
            story.append(Paragraph(f"<b>{bid}. {title}</b>", item_title_style))
            evidence = b.get("evidence", []) or ["No detailed evidence recorded"]
            ev_summary = _esc(evidence[0])
            why_txt = _esc(b.get("confidence_reason", ""))
            conf_val = b.get('confidence', 50)
            story.append(Paragraph(f"<b>Top evidence signal:</b> {ev_summary} <b>Why \"possible\" not confirmed:</b> {why_txt} <b>Confidence:</b> {conf_val}%", body_style))
            story.append(Paragraph(f"See Evidence Traceability for the complete {len(evidence)}-item evidence chain.", body_style))
            story.append(Spacer(1, 4))

        story.append(HRFlowable(width="100%", thickness=0.75, color=colors.gray, spaceAfter=10, spaceBefore=8))

        # ----------------------------------------------------
        # 3. ROOT CAUSES (Tier 3)
        # ----------------------------------------------------
        story.append(Paragraph("3. ROOT CAUSES (evidence directly supports the explanation)", section_heading_style))

        for c in tier3:
            cid = _esc(c.get('id', 'C?'))
            title = _esc(c.get('title', 'Root Cause'))
            root_cause = _esc(c.get('root_cause', ''))
            rec_action = _esc(c.get('recommended_action', ''))
            conf_reason = _esc(c.get('confidence_reason', ''))
            conf_val = c.get('confidence', 70)
            story.append(Paragraph(f"<b>{cid}. {title}</b>", item_title_style))
            story.append(Paragraph(f"<b>Root cause:</b> {root_cause}", body_style))
            story.append(Paragraph(f"<b>Recommended action:</b> {rec_action}", body_style))
            story.append(Paragraph(f"<b>Confidence:</b> {conf_val}% ({conf_reason})", body_style))
            story.append(Spacer(1, 6))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=8, spaceBefore=6))

        # ----------------------------------------------------
        # 4. POSSIBLE ROOT CAUSES (Tier 4)
        # ----------------------------------------------------
        story.append(Paragraph("4. POSSIBLE ROOT CAUSES (plausible, but not fully confirmed by available evidence)", section_heading_style))

        for d in tier4:
            did = _esc(d.get('id', 'D?'))
            title = _esc(d.get('title', 'Possible Root Cause'))
            hypo = _esc(d.get('hypothesis', ''))
            confirm_it = _esc(d.get('what_would_confirm_it', ''))
            conf_val = d.get('confidence', 50)
            story.append(Paragraph(f"<b>{did}. {title}</b>", item_title_style))
            story.append(Paragraph(f"<b>Hypothesis:</b> {hypo}", body_style))
            story.append(Paragraph(f"<b>What would confirm it:</b> {confirm_it}", body_style))
            story.append(Paragraph(f"<b>Confidence:</b> {conf_val}%", body_style))
            story.append(Spacer(1, 6))

        story.append(HRFlowable(width="100%", thickness=0.75, color=colors.gray, spaceAfter=10, spaceBefore=8))

        # ----------------------------------------------------
        # 5. PRIORITIZED ACTION PLAN
        # ----------------------------------------------------
        story.append(Paragraph("5. PRIORITIZED ACTION PLAN", section_heading_style))
        action_data = [[
            Paragraph("ID / Finding", table_header_style),
            Paragraph("Priority / Owner / Status", table_header_style),
            Paragraph("Action", table_header_style),
            Paragraph("Rollback", table_header_style),
            Paragraph("Verification", table_header_style),
        ]]
        for item in action_items:
            action_data.append([
                Paragraph(_esc(f"{item['id']} / {', '.join(item['finding_ids'])}"), table_cell_bold),
                Paragraph(_esc(f"{item['priority']} / {item['owner']} / {item['status']}"), table_cell_style),
                Paragraph(_esc(item["action"]), table_cell_style),
                Paragraph(_esc(item["rollback"]), table_cell_style),
                Paragraph(_esc(item["verification"]), table_cell_style),
            ])
        action_table = Table(action_data, colWidths=[60, 90, 130, 120, 120], repeatRows=1)
        action_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(action_table)
        story.append(Spacer(1, 14))

        # ----------------------------------------------------
        # 6. SCORECARD (matches hackathon required output shape)
        # ----------------------------------------------------
        story.append(Paragraph("6. SCORECARD (matches the hackathon's required output shape)", section_heading_style))

        scorecard_rows = generate_scorecard_data(diagnosis_results, rca_results)
        # Columns: # (24), Issue (95), Evidence (170), Category (65), Confidence (50), Action (120) = 524
        table_data = [
            [
                Paragraph("<b>#</b>", table_header_style),
                Paragraph("<b>Issue</b>", table_header_style),
                Paragraph("<b>Evidence (top signal)</b>", table_header_style),
                Paragraph("<b>Category</b>", table_header_style),
                Paragraph("<b>Confidence</b>", table_header_style),
                Paragraph("<b>Recommended Action</b>", table_header_style),
            ]
        ]

        for r in scorecard_rows:
            table_data.append([
                Paragraph(_esc(r.get("id", "")), table_cell_bold),
                Paragraph(_esc(r.get("issue", "")), table_cell_style),
                Paragraph(_esc(r.get("evidence_top_signal", "")), table_cell_style),
                Paragraph(_esc(r.get("category", "")), table_cell_style),
                Paragraph(_esc(r.get("confidence", "")), table_cell_style),
                Paragraph(_esc(r.get("recommended_action", "")), table_cell_style),
            ])

        t_scorecard = Table(table_data, colWidths=[24, 95, 170, 65, 50, 120])
        t_scorecard.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_scorecard)
        story.append(Spacer(1, 14))

        # ----------------------------------------------------
        # 7. CONSOLIDATED CASE TABLE
        # ----------------------------------------------------
        story.append(Paragraph("7. CONSOLIDATED CASE TABLE — Anomaly → Evidence → Root Cause → Remediation", section_heading_style))
        story.append(Paragraph(
            "<i>This is the single table a Local RCA Agent should be able to produce end-to-end from the "
            "Diagnosis Component's output. Where a root cause is still a hypothesis (not fully confirmed), "
            "it's marked (unconfirmed) — the RCA Agent should always be honest about this rather than "
            "presenting a guess as fact.</i>",
            body_style
        ))
        story.append(Spacer(1, 4))

        # Root cause mapping
        root_cause_map = {}
        for c in tier3:
            target_id = c.get("target_anomaly_id", c.get("id", ""))
            root_cause_map[target_id] = (_esc(c.get("root_cause", "")), _esc(c.get("recommended_action", "")), f"{c.get('confidence', 70)}%")
        for d in tier4:
            target_id = d.get("target_anomaly_id", d.get("id", ""))
            root_cause_map[target_id] = (f"{_esc(d.get('hypothesis', ''))} <i>(unconfirmed)</i>", _esc(d.get("recommended_action", "")), f"{d.get('confidence', 50)}%")

        # Consolidated Table Columns: # (20), Anomaly (90), Evidence (150), Root Cause (125), Remediation (100), Conf (35) = 520
        case_data = [
            [
                Paragraph("<b>#</b>", table_header_style),
                Paragraph("<b>Anomaly</b>", table_header_style),
                Paragraph("<b>Evidence</b>", table_header_style),
                Paragraph("<b>Root Cause</b>", table_header_style),
                Paragraph("<b>Recommended Remediation</b>", table_header_style),
                Paragraph("<b>Confidence</b>", table_header_style),
            ]
        ]

        # Add Tier 1 Anomalies
        for a in tier1:
            aid = _esc(a.get("id", ""))
            title = _esc(a.get("title", ""))
            evidence_count = len(a.get("evidence", []))
            ev_str = _esc(f"See Evidence Traceability ({a.get('id', '')}; {evidence_count} evidence items)")
            rc_info = root_cause_map.get(a.get("id", ""), ("Under investigation", "Monitor system", f"{a.get('confidence', 80)}%"))
            case_data.append([
                Paragraph(aid, table_cell_bold),
                Paragraph(title, table_cell_style),
                Paragraph(ev_str, table_cell_style),
                Paragraph(rc_info[0], table_cell_style),
                Paragraph(rc_info[1], table_cell_style),
                Paragraph(rc_info[2], table_cell_style),
            ])

        # Add Tier 2 Anomalies
        for b in tier2:
            bid = _esc(b.get("id", ""))
            title = _esc(b.get("title", ""))
            evidence_count = len(b.get("evidence", []))
            ev_str = _esc(f"See Evidence Traceability ({b.get('id', '')}; {evidence_count} evidence items)")
            rc_info = root_cause_map.get(b.get("id", ""), ("Pending longer telemetry window", "Extend observation window", f"{b.get('confidence', 50)}%"))
            case_data.append([
                Paragraph(bid, table_cell_bold),
                Paragraph(title, table_cell_style),
                Paragraph(ev_str, table_cell_style),
                Paragraph(rc_info[0], table_cell_style),
                Paragraph(rc_info[1], table_cell_style),
                Paragraph(rc_info[2], table_cell_style),
            ])

        t_case = Table(case_data, colWidths=[20, 90, 150, 125, 100, 35])
        t_case.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t_case)

        # Build Document
        doc.build(story)
        return output_path
