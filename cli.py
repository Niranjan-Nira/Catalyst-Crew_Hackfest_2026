import argparse
import sys
from pathlib import Path

from src.diagnosis import DiagnosisEngine
from src.rca import LocalRCAAgent
from src.reporting import CaseReportBuilder, PDFReportGenerator
from src.self_healing import SelfHealingScriptGenerator

def main():
    parser = argparse.ArgumentParser(description="Endpoint AI — The Self-Healing Intelligent Workstation (CLI)")
    parser.add_argument("--data", type=str, default="Input file", help="Path to diagnostic logs folder (e.g. 'Input file')")
    parser.add_argument("--output", type=str, default="output/case_report.md", help="Path to save generated Markdown report")
    parser.add_argument("--pdf", type=str, default="output/Anomaly_and_RCA_result.pdf", help="Path to save generated PDF report")
    parser.add_argument("--scripts", action="store_true", default=True, help="Generate self-healing PowerShell scripts into output/scripts/ (default: True)")
    parser.add_argument("--no-scripts", action="store_false", dest="scripts", help="Skip generating self-healing scripts")
    args = parser.parse_args()

    data_dir = Path(args.data)
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Analyzing diagnostic data from: {data_dir.resolve()}...")

    # Phase 1: Diagnosis Engine
    engine = DiagnosisEngine(data_dir)
    diag_res = engine.run()
    t1_count = len(diag_res["tier1_anomalies"])
    t2_count = len(diag_res["tier2_possible_anomalies"])
    print(f"[+] Diagnosis Complete: {t1_count} Tier-1 Anomalies, {t2_count} Tier-2 Possible Anomalies identified.")

    # Phase 2: Local RCA Agent
    print("[*] Running Local RCA Agent with Grounded RAG...")
    agent = LocalRCAAgent(data_dir)
    rca_res = agent.run_rca(diag_res)
    t3_count = len(rca_res["tier3_root_causes"])
    t4_count = len(rca_res["tier4_possible_root_causes"])
    print(f"[+] RCA Complete: {t3_count} Tier-3 Root Causes, {t4_count} Tier-4 Hypotheses generated.")

    # Phase 3: Reporting (Markdown & PDF)
    device_name = data_dir.name
    report_md = CaseReportBuilder.build_markdown_report(device_name, diag_res, rca_res)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")
    print(f"[+] Case Report (Markdown) successfully generated: {out_path.resolve()}")

    pdf_path = Path(args.pdf)
    PDFReportGenerator.generate_pdf(pdf_path, diag_res, rca_res, title_text="Sample Anomaly and RCA")
    print(f"[+] Official PDF Case Report successfully generated: {pdf_path.resolve()}")

    # Phase 4: Self-Healing Scripts
    if args.scripts:
        scripts_dir = out_path.parent / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for c in rca_res["tier3_root_causes"]:
            script_data = SelfHealingScriptGenerator.generate_script_for_finding(
                c["id"], c["title"], c["recommended_action"]
            )
            script_file = scripts_dir / script_data["name"]
            script_file.write_text(script_data["code"], encoding="utf-8")
            print(f"[+] Self-Healing Script saved: {script_file.name}")

    print("[*] All tasks finished successfully.")

if __name__ == "__main__":
    main()
