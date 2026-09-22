import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.diagnosis import DiagnosisEngine
from src.rca import LocalRCAAgent
from src.reporting import CaseReportBuilder, PDFReportGenerator, generate_scorecard_data
from src.self_healing import SelfHealingScriptGenerator
from src.rag import retrieve_grounded_context

def test_input_file_diagnosis():
    data_dir = Path("Input file")
    assert data_dir.exists(), "Input file directory should exist"

    engine = DiagnosisEngine(data_dir)
    res = engine.run()

    assert len(res["tier1_anomalies"]) >= 4, f"Expected >= 4 Tier-1 anomalies, got {len(res['tier1_anomalies'])}"
    tier1_titles = [a["title"].lower() for a in res["tier1_anomalies"]]
    assert any("intel graphics" in t for t in tier1_titles), "Missing Intel Graphics display anomaly"
    assert any("crash cluster" in t for t in tier1_titles), "Missing crash cluster anomaly"
    assert any("powerpoint" in t for t in tier1_titles), "Missing PowerPoint version mismatch anomaly"
    assert any("watchdog" in t for t in tier1_titles), "Missing watchdog anomaly"
    assert len(res["tier2_possible_anomalies"]) >= 3, f"Expected >= 3 Tier-2 anomalies, got {len(res['tier2_possible_anomalies'])}"

def test_rca_agent_execution():
    data_dir = Path("Input file")
    engine = DiagnosisEngine(data_dir)
    diag_res = engine.run()

    agent = LocalRCAAgent(data_dir)
    rca_res = agent.run_rca(diag_res)

    assert len(rca_res["tier3_root_causes"]) >= 2
    assert len(rca_res["tier4_possible_root_causes"]) >= 2

    t3_titles = [c["title"].lower() for c in rca_res["tier3_root_causes"]]
    assert any("crash cluster" in t for t in t3_titles), "Missing crash cluster RCA"

def test_rag_retrieval():
    docs = retrieve_grounded_context("OFFICE_MODULE_VERSION_MISMATCH")
    assert len(docs) > 0, "RAG should retrieve at least one document"

def test_self_healing_scripts():
    script = SelfHealingScriptGenerator.generate_script_for_finding("C1", "crash cluster Spektion", "rollback")
    assert script["name"] == "Remediate-SpektionSensorHooking.ps1"
    assert "Stop-Service" in script["code"]

def test_report_builder():
    data_dir = Path("Input file")
    diag_res = DiagnosisEngine(data_dir).run()
    rca_res = LocalRCAAgent(data_dir).run_rca(diag_res)
    md = CaseReportBuilder.build_markdown_report("Input file", diag_res, rca_res)
    assert "# Diagnostic & Root Cause Analysis Case Report" in md
    assert "## 5. SCORECARD" in md
    assert "## 6. CONSOLIDATED CASE TABLE" in md

def test_pdf_generation():
    data_dir = Path("Input file")
    diag_res = DiagnosisEngine(data_dir).run()
    rca_res = LocalRCAAgent(data_dir).run_rca(diag_res)
    pdf_path = Path("output/test_output.pdf")
    generated = PDFReportGenerator.generate_pdf(pdf_path, diag_res, rca_res)
    assert generated.exists(), "PDF should exist"
    assert generated.stat().st_size > 5000, "PDF file should be non-trivial size"

def test_device_4_and_6():
    for dev_name in ["Device 4 - Full logs", "Device 6 - Full logs"]:
        dev_path = Path("Raw Data") / dev_name
        if dev_path.exists():
            diag_res = DiagnosisEngine(dev_path).run()
            assert "tier1_anomalies" in diag_res
            assert "tier2_possible_anomalies" in diag_res

if __name__ == "__main__":
    print("[*] Running all tests...")
    test_input_file_diagnosis()
    print("  [OK] test_input_file_diagnosis passed")
    test_rca_agent_execution()
    print("  [OK] test_rca_agent_execution passed")
    test_rag_retrieval()
    print("  [OK] test_rag_retrieval passed")
    test_self_healing_scripts()
    print("  [OK] test_self_healing_scripts passed")
    test_report_builder()
    print("  [OK] test_report_builder passed")
    test_pdf_generation()
    print("  [OK] test_pdf_generation passed")
    test_device_4_and_6()
    print("  [OK] test_device_4_and_6 passed")
    print("[+] ALL TESTS PASSED SUCCESSFULLY!")
