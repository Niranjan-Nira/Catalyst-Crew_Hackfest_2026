import json
from typing import Any, Dict

from .luna_client import LunaClient


def generate_luna_solution(
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a clear solution guide from local findings when Luna is enabled."""
    client = LunaClient()
    if not client.is_configured:
        return {
            "summary": "",
            "model_used": "Local RCA solution",
            "is_online": False,
            "error": "Luna is disabled or its API key is not configured.",
        }

    evidence = {
        "high_confidence_findings": diagnosis_results.get("tier1_anomalies", []),
        "possible_findings": diagnosis_results.get("tier2_possible_anomalies", []),
        "root_causes": rca_results.get("tier3_root_causes", []),
        "possible_root_causes": rca_results.get("tier4_possible_root_causes", []),
    }
    prompt = (
        "Create a clear, technically precise Endpoint AI solution guide from the local evidence below. "
        "Use only the supplied evidence. Do not invent facts. Distinguish confirmed findings from hypotheses. "
        "Use these headings: Executive diagnosis, Evidence, Likely cause, Recommended steps, "
        "Risk and rollback, Verification, and Limitations. Number the recommended steps and explain "
        "why each step is appropriate. Prefer safe, reversible actions and mention -WhatIf where relevant.\n\n"
        f"LOCAL CASE EVIDENCE:\n{json.dumps(evidence, indent=2, default=str)}"
    )
    system_prompt = (
        "You are Luna 5.6 assisting with endpoint diagnostics. Produce concise, clear guidance for a technician. "
        "Never claim certainty beyond the evidence and never recommend destructive changes without a warning."
    )
    output = client.generate_rca_reasoning(prompt, system_prompt=system_prompt)
    if not output or len(output.strip()) < 50:
        return {
            "summary": "",
            "model_used": client.model,
            "is_online": False,
            "error": "Luna did not return a usable solution guide.",
        }
    return {
        "summary": output.strip(),
        "model_used": client.model,
        "is_online": True,
        "error": "",
    }