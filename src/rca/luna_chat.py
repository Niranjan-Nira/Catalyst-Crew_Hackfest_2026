import json
from typing import Any, Dict, List

from .luna_client import LunaClient


def answer_case_question(
    question: str,
    rag_results: List[Dict[str, Any]],
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any],
    conversation: List[Dict[str, str]] | None = None,
) -> str | None:
    """Answer a case question with local RAG context and Luna's available knowledge."""
    client = LunaClient()
    if not client.is_configured:
        return None

    rag_context = "\n\n---\n\n".join(
        f"[{item.get('doc_title', 'Knowledge source')}] {item.get('title', '')}\n"
        f"Source: {item.get('source', 'Not recorded')}\n{item.get('content', item.get('snippet', ''))}"
        for item in rag_results
    )
    case_context = json.dumps({
        "high_confidence_findings": diagnosis_results.get("tier1_anomalies", []),
        "possible_findings": diagnosis_results.get("tier2_possible_anomalies", []),
        "root_causes": rca_results.get("tier3_root_causes", []),
        "possible_root_causes": rca_results.get("tier4_possible_root_causes", []),
    }, indent=2, default=str)
    history = "\n".join(
        f"{message.get('role', 'user').upper()}: {message.get('content', '')}"
        for message in (conversation or [])[-6:]
    )
    prompt = f"""Answer the technician's question clearly and directly.

Use the CASE EVIDENCE and LOCAL RAG CONTEXT first. You may use your current general/internet knowledge
for supplementary Windows troubleshooting information, but clearly label information that is not directly
supported by this case. Never invent telemetry, citations, or completed actions. Explain uncertainty,
give numbered safe steps, include verification commands where useful, and mention rollback or risk before
changes. If the question asks for a conclusion, state the evidence and confidence.

CASE EVIDENCE:
{case_context}

LOCAL RAG CONTEXT:
{rag_context or 'No matching local knowledge was retrieved.'}

RECENT CHAT:
{history or 'No previous conversation.'}

TECHNICIAN QUESTION:
{question}
"""
    system_prompt = (
        "You are Luna 5.6, a precise Windows endpoint diagnostics assistant. "
        "Respond in clear Markdown. Separate case evidence from general guidance. "
        "Do not claim to have browsed the internet unless the service actually provides that capability."
    )
    return client.generate_rca_reasoning(prompt, system_prompt=system_prompt)