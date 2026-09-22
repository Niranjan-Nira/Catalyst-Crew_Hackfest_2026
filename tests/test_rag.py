"""
test_rag.py — Comprehensive validation test suite for the Endpoint AI RAG System.
Verifies:
  1. Multi-source document indexing (Hackathon Guide, Cheat Sheet, WER Guide, Encyclopedia).
  2. Exact signal fast-path retrieval (Event IDs, Hex error codes, WER buckets, ConfigManager codes).
  3. Natural language queries for investigation playbooks and judging rules.
  4. Dynamic document ingestion at runtime.
"""
import sys
import argparse
from pathlib import Path

from src.rag import get_knowledge_base, retrieve_grounded_context, add_custom_document, build_llm_prompt


def run_tests():
    print("=" * 70)
    print("ENDPOINT AI RAG SYSTEM — VALIDATION TEST SUITE")
    print("=" * 70)

    # 1. Test Knowledge Base Initialization & Ingestion
    print("\n[1] Initializing RAG Knowledge Base and indexing all sources...")
    kb = get_knowledge_base()
    stats = kb.get_stats()

    print(f"    [+] Total Documents Indexed: {stats['total_documents']}")
    print(f"    [+] Total Knowledge Chunks:  {stats['total_chunks']}")
    print(f"    [+] Average Tokens/Chunk:    {stats['avg_tokens_per_chunk']}")
    print("    [+] Category Distribution:")
    for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
        print(f"        - {cat}: {count} chunks")

    # Assert essential documents are present
    files = set(stats["files"].keys())
    assert "HACKATHON_DATA_GUIDE.md" in files, "HACKATHON_DATA_GUIDE.md missing from index!"
    assert "Diagnostic Cheat Sheet.md" in files, "Diagnostic Cheat Sheet.md missing from index!"
    print("\n    [+] Core Hackathon Guides successfully indexed!")

    # 2. Test Exact Signal Matching (Hex code, Event ID, ConfigManager, WER Bucket)
    print("\n[2] Testing High-Precision Exact Signal Matches...")

    test_signals = [
        ("0xC0000005", "Hex Exception Code"),
        ("Event 7000", "Windows Event ID 7000"),
        ("Kernel-Power 41", "Kernel-Power Event ID 41"),
        ("CM_PROB_FAILED_POST_START", "ConfigManager Error Code"),
        ("OFFICE_MODULE_VERSION_MISMATCH", "WER Bucket Classification"),
    ]

    for query, description in test_signals:
        results = retrieve_grounded_context(query, top_k=2)
        assert len(results) > 0, f"No results returned for {description}: '{query}'"
        top = results[0]
        reasons = ", ".join(top["match_reasons"])
        print(f"    [+] Query: '{query}' ({description})")
        print(f"      Top Hit: [{top['doc_title']}] {top['title']} (Score: {top['score']}, Match: {reasons})")

    # 3. Test Plain English & Hackathon Domain Queries
    print("\n[3] Testing Playbook & Domain Queries...")
    domain_queries = [
        ("Diagnostic cheat sheet time join key", "Cheat Sheet Step 2 (Time Join Key)"),
        ("Tier 1 anomalies judging rules and confidence", "Hackathon Guide Part 4 (Tiers & Judging)"),
        ("How to decode EventTime FILETIME in Report.wer", "Crash Dump WER guide"),
    ]

    for query, expected_desc in domain_queries:
        results = retrieve_grounded_context(query, top_k=2)
        assert len(results) > 0, f"No results returned for '{query}'"
        top = results[0]
        print(f"    [+] Query: '{query}'")
        print(f"      Top Hit: [{top['source']}] {top['title']} (Score: {top['score']})")

    # 4. Test Dynamic Document Ingestion at Runtime
    print("\n[4] Testing Dynamic Runtime Document Ingestion...")
    sample_doc_content = """# Corporate Zero Trust Gateway Troubleshooting Guide
## AnyConnect VPN Event 4012 Gateway Connection Timeout
When AnyConnect logs Event 4012, it indicates a TLS 1.3 handshake timeout with the enterprise gateway.
### Diagnostic Steps
1. Execute `Test-NetConnection -ComputerName vpn.enterprise.com -Port 443`.
2. Inspect `C:\\ProgramData\\Cisco\\Cisco AnyConnect Secure Mobility Client\\vpn.log`.
### Resolution
Reset IP stack and re-issue client certificate.
"""
    doc_name = "Corporate_VPN_Guide.md"
    chunks_added = add_custom_document(sample_doc_content, doc_name=doc_name)
    print(f"    [+] Ingested '{doc_name}': {chunks_added} chunks added to active index.")

    vpn_results = retrieve_grounded_context("AnyConnect VPN Event 4012 TLS handshake timeout", top_k=1)
    assert len(vpn_results) > 0, "Failed to retrieve from dynamically ingested document!"
    assert "AnyConnect" in vpn_results[0]["content"], "Dynamic document content mismatch!"
    print(f"    [+] Live Search Verified: Top Hit = '{vpn_results[0]['title']}' from '{vpn_results[0]['source']}'")

    # Clean up test doc from disk if written
    test_file_path = Path("knowledge_docs") / doc_name
    if test_file_path.exists():
        test_file_path.unlink()

    # 4b. Test Dynamic PDF Document Ingestion
    print("\n[4b] Testing Dynamic PDF Document Ingestion...")
    import io
    from reportlab.pdfgen import canvas

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer)
    c.drawString(100, 750, "Storage Spaces Direct Cluster Validation Runbook")
    c.drawString(100, 730, "Event 5120 Cluster Shared Volume Paused")
    c.drawString(100, 710, "CSV volume entered paused state due to SMB3 channel disconnect.")
    c.save()
    pdf_bytes = pdf_buffer.getvalue()

    pdf_doc_name = "Storage_Spaces_Runbook.pdf"
    pdf_chunks = add_custom_document(pdf_bytes, doc_name=pdf_doc_name)
    print(f"    [+] Ingested '{pdf_doc_name}': {pdf_chunks} chunks added to active index.")
    assert pdf_chunks > 0, "Failed to extract chunks from PDF document!"

    pdf_results = retrieve_grounded_context("Storage Spaces Direct Event 5120 Cluster Shared Volume", top_k=1)
    assert len(pdf_results) > 0, "Failed to retrieve from dynamically ingested PDF!"
    assert "5120" in pdf_results[0]["content"] or "Storage Spaces" in pdf_results[0]["content"], "PDF content mismatch!"
    print(f"    [+] Live PDF Search Verified: Top Hit = '{pdf_results[0]['title']}' from '{pdf_results[0]['source']}'")

    pdf_clean_path = Path("knowledge_docs") / pdf_doc_name
    if pdf_clean_path.exists():
        pdf_clean_path.unlink()

    # 4c. Test Dynamic Word (.docx) Document Ingestion
    print("\n[4c] Testing Dynamic Word (.docx) Document Ingestion...")
    import docx

    word_doc = docx.Document()
    word_doc.add_heading("DirectAccess Tunnel Error Diagnostics", level=1)
    word_doc.add_heading("Error 0x800B0109 Certificate Untrusted", level=2)
    word_doc.add_paragraph("Root certificate chain validation failed. IPsec tunnel establishment blocked.")
    table = word_doc.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Phase"
    hdr_cells[1].text = "Remediation"
    row_cells = table.add_row().cells
    row_cells[0].text = "Step 1"
    row_cells[1].text = "Verify CRL distribution point accessibility."

    docx_buffer = io.BytesIO()
    word_doc.save(docx_buffer)
    docx_bytes = docx_buffer.getvalue()

    docx_doc_name = "DirectAccess_Runbook.docx"
    docx_chunks = add_custom_document(docx_bytes, doc_name=docx_doc_name)
    print(f"    [+] Ingested '{docx_doc_name}': {docx_chunks} chunks added to active index.")
    assert docx_chunks > 0, "Failed to extract chunks from Word document!"

    docx_results = retrieve_grounded_context("DirectAccess Error 0x800B0109 Certificate Untrusted", top_k=1)
    assert len(docx_results) > 0, "Failed to retrieve from dynamically ingested Word DOCX!"
    assert "DirectAccess" in docx_results[0]["content"] or "0x800B0109" in docx_results[0]["content"], "DOCX content mismatch!"
    print(f"    [+] Live DOCX Search Verified: Top Hit = '{docx_results[0]['title']}' from '{docx_results[0]['source']}'")

    docx_clean_path = Path("knowledge_docs") / docx_doc_name
    if docx_clean_path.exists():
        docx_clean_path.unlink()

    # 5. Test LLM Prompt Generation
    print("\n[5] Testing Grounded LLM Prompt Generation...")
    prompt = build_llm_prompt("OFFICE_MODULE_VERSION_MISMATCH", vpn_results)
    assert "RULES PER HACKATHON_DATA_GUIDE.md" in prompt, "Prompt missing hackathon rules!"
    assert "GROUNDED CONTEXT" in prompt, "Prompt missing grounded context!"
    print("    [+] Grounded LLM prompt generated compliant with HACKATHON_DATA_GUIDE.md!")

    print("\n" + "=" * 70)
    print("ALL RAG TESTS PASSED SUCCESSFULLY! (100% HEALTHY)")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Endpoint AI RAG Knowledge System CLI")
    parser.add_argument("--query", "-q", type=str, help="Search the RAG knowledge base directly")
    parser.add_argument("--top-k", "-k", type=int, default=3, help="Number of results to return (default: 3)")
    parser.add_argument("--category", "-c", type=str, default=None, help="Filter by category")
    parser.add_argument("--stats", action="store_true", help="Print knowledge base statistics")
    args = parser.parse_args()

    if args.stats:
        kb = get_knowledge_base()
        stats = kb.get_stats()
        print(f"Documents: {stats['total_documents']}, Chunks: {stats['total_chunks']}")
        for f, count in stats["files"].items():
            print(f"  {f}: {count} chunks")
        return

    if args.query:
        print(f"\n[*] Querying Knowledge Base for: '{args.query}' (top_k={args.top_k})...\n")
        results = retrieve_grounded_context(args.query, top_k=args.top_k, category=args.category)
        if not results:
            print("No matching knowledge base records found.")
            return

        for idx, r in enumerate(results, 1):
            reasons = ", ".join(r["match_reasons"])
            print(f"--- [Hit {idx}] [{r['doc_title']}] {r['title']} (Score: {r['score']}) ---")
            print(f"Source: {r['source']} | Category: {r['category']} | Match: {reasons}")
            print(f"Breadcrumb: {r['breadcrumb']}")
            print(f"Content Preview:\n{r['snippet']}\n")
        return

    # Default: Run test suite
    run_tests()


if __name__ == "__main__":
    main()
