import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Reddit import search_reddit_qa
from src.reddit_assistant import extract_primary_issue, summarize_reddit_solutions_with_luna
from src.diagnosis import DiagnosisEngine
from src.rca import LocalRCAAgent


def test_extract_primary_issue():
    data_dir = Path("Input file")
    assert data_dir.exists(), "Input file directory must exist"

    diag_res = DiagnosisEngine(data_dir).run()
    rca_res = LocalRCAAgent(data_dir).run_rca(diag_res)

    issue_info = extract_primary_issue(diag_res, rca_res)
    assert issue_info is not None
    assert "primary_title" in issue_info
    assert "query" in issue_info
    assert issue_info["query"].lower().startswith("how to solve")
    assert len(issue_info["candidates"]) > 0
    print(f"[+] Extracted primary query: {issue_info['query']}")


def test_reddit_search_and_luna_summarize():
    query = "How to solve application crash 0xC0000005"
    results = search_reddit_qa(query, limit=2)
    assert isinstance(results, list)
    assert len(results) > 0, "Should retrieve at least one Reddit thread"
    first = results[0]
    assert "title" in first
    assert "subreddit" in first
    assert "url" in first
    assert "best_answer" in first
    print(f"[+] Reddit returned {len(results)} threads. Top: {first['title']} ({first['subreddit']})")

    # Test Luna summarization
    summary = summarize_reddit_solutions_with_luna(query, results, issue_details="Memory access violation 0xC0000005")
    assert summary is not None
    assert "summary" in summary
    assert "model_used" in summary
    assert len(summary["summary"]) > 50
    print(f"[+] Luna summary generated using {summary['model_used']}")


if __name__ == "__main__":
    print("[*] Testing extract_primary_issue...")
    test_extract_primary_issue()
    print("[*] Testing reddit_search_and_luna_summarize...")
    test_reddit_search_and_luna_summarize()
    print("[+] All Reddit integration tests passed successfully!")
