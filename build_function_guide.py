from pathlib import Path
import re
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
INVENTORY = Path(r"c:\Users\eni4001\AppData\Roaming\Code\User\workspaceStorage\2b5cfeaef9170dc39f1cd1837cf1d405\GitHub.copilot-chat\chat-session-resources\85acff70-4dc3-48a9-b17f-7c07c2a6a947\call_2kR4xcPAPuvhEKgV5lF829LV__vscode-1790154656612\content.txt")
OUTPUT = ROOT / "output" / "Hackfest_2026_Function_Guide.docx"

CATEGORY_ADVANTAGES = {
    "Public detector": "Turns raw endpoint data into a focused finding that can be prioritized and investigated.",
    "Public parser": "Normalizes inconsistent Windows exports so downstream analysis can use one predictable structure.",
    "Public utility": "Centralizes a recurring operation, reducing duplicated logic and inconsistent behavior.",
    "Public correlator": "Connects related evidence across files or time, improving root-cause confidence.",
    "Public method": "Provides a stable module interface and keeps the workflow organized around a clear responsibility.",
    "Private helper": "Keeps specialized implementation detail out of the public API and makes the parent workflow easier to read.",
    "Private lifecycle method": "Controls internal state consistently while keeping setup and indexing behavior encapsulated.",
    "Private loader": "Loads supporting data in one place and allows the main workflow to stay focused on analysis.",
    "Private formatter": "Keeps output consistent and makes results easier for people and downstream systems to consume.",
    "Private builder": "Creates reusable structured output without spreading report-specific logic across the application.",
    "Private report builder": "Converts analysis results into a repeatable export contract for reports and integrations.",
    "Private generated helper": "Provides a reusable presentation component while keeping document generation maintainable.",
    "Private validation helper": "Prevents malformed or partial data from breaking report generation.",
    "Private classifier": "Applies a consistent rule for routing work to the right team or priority.",
    "Private scorer": "Makes ranking decisions repeatable and easier to inspect.",
    "Private selector": "Reduces a large set of candidates to the most useful issue for the next workflow step.",
    "Public chunker": "Preserves context while splitting documents, improving retrieval quality and citation traceability.",
    "Public accessor": "Provides one shared service instance and avoids repeated initialization cost.",
    "Public retriever": "Finds relevant grounded knowledge so generated explanations stay connected to project evidence.",
    "Public query helper": "Improves search recall by adding domain terminology that users may not know to include.",
    "Public prompt generator": "Creates consistent, evidence-focused prompts that guide reliable RCA output.",
    "Public generated-output method": "Produces a reusable artifact for technicians, reviewers, or automated systems.",
    "Public generated-output function": "Turns analysis into a practical guide that can be shared or acted on.",
    "Public integration": "Connects the diagnostic workflow to an external or conversational capability.",
    "Public formatter": "Presents complex diagnostic results in a concise form suitable for users.",
    "Public selector": "Identifies the most actionable issue and reduces unnecessary investigation effort.",
    "Public conversion helper": "Converts platform-specific values into standard Python values for reliable comparison and sorting.",
    "Public dispatcher": "Routes different input types to the correct parser without duplicating file-detection logic.",
    "Public CLI helper": "Makes the capability available from a terminal workflow for repeatable troubleshooting.",
    "Public integration": "Adds an optional external knowledge path while keeping the core diagnostic workflow usable.",
}


def set_cell_shading(cell, fill):
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = tcPr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcPr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        if edge in kwargs:
            tag = "w:" + edge
            element = borders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                borders.append(element)
            for key in ["val", "sz", "color", "space"]:
                if key in kwargs[edge]:
                    element.set(qn("w:" + key), str(kwargs[edge][key]))


def parse_inventory(text):
    modules = []
    current_group = "Project Functions"
    current_module = None
    for line in text.splitlines():
        if line.startswith("## "):
            current_group = line[3:].strip()
        elif line.startswith("### "):
            current_module = {"group": current_group, "name": line[4:].strip(), "functions": [], "overview": ""}
            modules.append(current_module)
        elif current_module and line.startswith("| `"):
            cells = [part.strip() for part in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0] != "Definition":
                current_module["functions"].append({
                    "name": cells[0].strip("`") ,
                    "purpose": cells[1],
                    "classification": cells[2],
                })
        elif current_module and line.startswith("| Streamlit"):
            current_module["functions"].append({
                "name": "Streamlit application body",
                "purpose": "Builds the interactive diagnosis, RCA, reporting, RAG, Reddit, and self-healing user interface.",
                "classification": "Application entrypoint",
            })
    return modules


def clean_text(value):
    return re.sub(r"\s+", " ", value).strip()


def explain_help(function, module):
    purpose = function["purpose"].lower()
    name = function["name"]
    if "parse" in name or "extract" in name or "load" in name:
        return "It prepares source data for later diagnosis by turning files, records, or raw values into structured information."
    if "detect" in name or "anomal" in purpose or "cluster" in name:
        return "It gives the diagnostic engine a focused signal instead of requiring technicians to inspect every raw record manually."
    if "report" in name or "scorecard" in name or "chart" in name:
        return "It makes technical findings easier to review, share, compare, and hand off to support or incident-management systems."
    if "rca" in name.lower() or "root cause" in purpose or "correlat" in name:
        return "It connects evidence and hypotheses so the team can move from symptoms toward a defensible explanation."
    if "retrieve" in name or "chunk" in name or "prompt" in name or "knowledge" in purpose:
        return "It improves access to project guidance and keeps generated answers grounded in relevant technical material."
    if "script" in name or "remediat" in purpose or "self-heal" in purpose:
        return "It turns a recommendation into a repeatable operational step while supporting safer technician execution."
    if "reddit" in name.lower() or "community" in purpose:
        return "It adds an optional external troubleshooting perspective without replacing the local evidence-based diagnosis."
    return "It supports the surrounding workflow by keeping this responsibility in one clear, reusable function."


def add_bullet(doc, label, text):
    paragraph = doc.add_paragraph(style="List Bullet")
    run = paragraph.add_run(label + ": ")
    run.bold = True
    paragraph.add_run(text)


def add_function_entry(doc, function, module):
    heading = doc.add_paragraph(style="Heading 3")
    run = heading.add_run(function["name"] + "()")
    run.font.name = "Aptos Display"
    run.font.color.rgb = RGBColor(15, 118, 110)
    add_bullet(doc, "What it does", clean_text(function["purpose"]))
    add_bullet(doc, "How it helps", explain_help(function, module))
    advantage = CATEGORY_ADVANTAGES.get(function["classification"], "Keeps the system modular, easier to test, and easier for another team member to extend.")
    add_bullet(doc, "Advantage", advantage)
    classification = doc.add_paragraph()
    classification.paragraph_format.space_after = Pt(6)
    r = classification.add_run("Type: " + function["classification"])
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(100, 116, 139)


def configure_document(doc):
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor(30, 41, 59)
    normal.paragraph_format.space_after = Pt(5)
    for style_name, size, color in [("Title", 30, "0F172A"), ("Heading 1", 19, "0F766E"), ("Heading 2", 14, "2563EB"), ("Heading 3", 11, "0F766E")]:
        style = styles[style_name]
        style.font.name = "Aptos Display"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("Hackfest 2026 | Function Guide | ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)


def build_document(modules):
    doc = Document()
    configure_document(doc)

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("Hackfest 2026\nFunction Guide")
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("What each function does, how it helps, and why it matters").italic = True
    doc.add_paragraph()

    summary = doc.add_table(rows=1, cols=3)
    summary.alignment = WD_TABLE_ALIGNMENT.CENTER
    summary.autofit = True
    total = sum(len(m["functions"]) for m in modules)
    values = [("99", "documented definitions"), (str(len(modules)), "modules covered"), ("3", "export formats covered")]
    for cell, (number, label) in zip(summary.rows[0].cells, values):
        set_cell_shading(cell, "E6FFFB")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(number + "\n")
        r.bold = True
        r.font.size = Pt(18)
        r.font.color.rgb = RGBColor(15, 118, 110)
        p.add_run(label).font.size = Pt(9)
    doc.add_paragraph()

    doc.add_heading("How to use this guide", level=1)
    doc.add_paragraph("This document is a team reference for the Python functions in the Hackfest 2026 diagnostic platform. Each entry is intentionally concise so a new contributor can understand the function’s role without reading the entire implementation first.")
    add_bullet(doc, "Start with the workflow", "DiagnosisEngine.run() coordinates the main evidence-to-finding path, followed by LocalRCAAgent.run_rca() and the reporting or remediation functions.")
    add_bullet(doc, "Use the module sections", "Each section groups functions by the part of the system they support: parsing, diagnosis, retrieval, RCA, reporting, or integrations.")
    add_bullet(doc, "Treat optional integrations as optional", "Luna and Reddit functions enrich the experience, but the local diagnostic and reporting path remains the core workflow.")

    doc.add_heading("System workflow at a glance", level=1)
    workflow = doc.add_table(rows=1, cols=5)
    workflow.alignment = WD_TABLE_ALIGNMENT.CENTER
    workflow.style = "Table Grid"
    stages = [("1. Input", "ZIPs, folders, CSV, WER"), ("2. Parse", "Normalize evidence"), ("3. Diagnose", "Find anomalies"), ("4. RCA", "Explain causes"), ("5. Deliver", "Reports and actions")]
    for cell, (stage, detail) in zip(workflow.rows[0].cells, stages):
        set_cell_shading(cell, "0F766E")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(stage + "\n")
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        p.add_run(detail).font.color.rgb = RGBColor(255, 255, 255)
        p.runs[-1].font.size = Pt(8)
    doc.add_paragraph()

    doc.add_heading("Contents", level=1)
    for module in modules:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(module["name"].replace("[", "").replace("]", "")).bold = True
        p.add_run(f"  ({len(module['functions'])} functions)")

    doc.add_page_break()
    current_group = None
    for module in modules:
        if module["group"] != current_group:
            current_group = module["group"]
            doc.add_heading(current_group, level=1)
        doc.add_heading(module["name"], level=2)
        source = doc.add_paragraph()
        source.add_run("Module role: ").bold = True
        source.add_run("This module contains the functions responsible for " + module["name"].split("/")[-1].replace(".py", "").replace("_", " ") + ".")
        for function in module["functions"]:
            add_function_entry(doc, function, module)
        doc.add_paragraph()

    doc.add_heading("Team conventions and extension guidance", level=1)
    add_bullet(doc, "Keep parsers focused", "A parser should normalize source data; detection and RCA logic should remain in diagnosis or RCA modules.")
    add_bullet(doc, "Preserve structured outputs", "Findings should retain IDs, evidence, source files, timestamps, confidence, and confidence reasons so reports remain traceable.")
    add_bullet(doc, "Prefer safe remediation", "Self-healing actions should remain reviewable, support WhatIf behavior where appropriate, and provide rollback or verification guidance.")
    add_bullet(doc, "Protect sensitive data", "Use report sanitization before sharing identifiers such as usernames, IP addresses, and local paths.")
    add_bullet(doc, "Test at the boundary", "When adding a function, include a focused test for its input/output contract and run the report or pipeline tests for cross-module changes.")

    doc.add_heading("Primary execution path", level=1)
    doc.add_paragraph("DiagnosisEngine.run() -> LocalRCAAgent.run_rca() -> CaseReportBuilder.build_markdown_report() / PDFReportGenerator.generate_pdf() / SIEM action export")
    doc.add_paragraph("This sequence is the shortest useful mental model for the team: collect and parse evidence, detect and rank anomalies, explain likely causes, then produce reports and safe next actions.")
    return doc


if __name__ == "__main__":
    modules = parse_inventory(INVENTORY.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = build_document(modules)
    document.save(OUTPUT)
    print(f"Created {OUTPUT} with {sum(len(m['functions']) for m in modules)} documented definitions")
