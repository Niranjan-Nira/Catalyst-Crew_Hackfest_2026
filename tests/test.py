"""Fast, network-independent end-to-end smoke test for Endpoint AI."""
from pathlib import Path

from src.diagnosis import DiagnosisEngine
from src.rca import LocalRCAAgent
from src.rag import retrieve_grounded_context
from src.reporting import CaseReportBuilder, PDFReportGenerator, generate_scorecard_data
from src.self_healing import SelfHealingScriptGenerator


def main() -> None:
    data_dir = Path("Input file")
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Diagnostic data directory not found: {data_dir}")

    diagnosis = DiagnosisEngine(data_dir).run()
    rca = LocalRCAAgent(data_dir).run_rca(diagnosis)

    assert diagnosis.get("tier1_anomalies"), "Diagnosis produced no Tier-1 anomalies"
    assert rca.get("tier3_root_causes"), "RCA produced no Tier-3 root causes"

    rag_results = retrieve_grounded_context("OFFICE_MODULE_VERSION_MISMATCH", top_k=1)
    assert rag_results, "RAG returned no result for a known signal"

    script = SelfHealingScriptGenerator.generate_script_for_finding(
        "C1", "crash cluster Spektion", "rollback"
    )
    assert script.get("code"), "Self-healing generator returned empty code"

    report = CaseReportBuilder.build_markdown_report(data_dir.name, diagnosis, rca)
    assert "## 5. SCORECARD" in report, "Markdown report is missing its scorecard"
    assert generate_scorecard_data(diagnosis, rca), "Scorecard contains no rows"

    pdf_path = Path("output") / "smoke_test_report.pdf"
    generated_pdf = PDFReportGenerator.generate_pdf(pdf_path, diagnosis, rca)
    assert generated_pdf.exists() and generated_pdf.stat().st_size > 5000, "PDF was not generated"
    generated_pdf.unlink()

    print("[+] Complete Endpoint AI smoke test passed")
    print(f"    Tier-1: {len(diagnosis['tier1_anomalies'])}")
    print(f"    Tier-3: {len(rca['tier3_root_causes'])}")
    print(f"    RAG results: {len(rag_results)}")
    print(f"    Scorecard rows: {len(generate_scorecard_data(diagnosis, rca))}")


if __name__ == "__main__":
    main()
