from typing import Dict, List, Any


def _as_dict(value: Any) -> Dict[str, Any]:
    """Keep exports usable when a partial or malformed result reaches the UI."""
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Dict[str, Any]]:
    """Return only mapping-shaped findings so report rows can be generated safely."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]

def generate_scorecard_data(
    diagnosis_results: Dict[str, Any],
    rca_results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generates structured rows matching the Hackathon's 5. SCORECARD requirement:
    Columns: #, Issue, Evidence (top signal), Category, Confidence, Recommended Action
    """
    rows = []

    diagnosis_results = _as_dict(diagnosis_results)
    rca_results = _as_dict(rca_results)
    tier1 = _as_list(diagnosis_results.get("tier1_anomalies", []))
    tier2 = _as_list(diagnosis_results.get("tier2_possible_anomalies", []))
    tier3 = _as_list(rca_results.get("tier3_root_causes", []))
    tier4 = _as_list(rca_results.get("tier4_possible_root_causes", []))

    # Map recommendations from RCA
    recs = {}
    for r in tier3:
        recs[r["target_anomaly_id"]] = r.get("recommended_action", "")
    for r in tier4:
        recs[r["target_anomaly_id"]] = r.get("recommended_action", "")

    # Tier 1 Anomalies
    for a in tier1:
        aid = a.get("id", "A?")
        title = a.get("title", "")
        top_ev = a["evidence"][0] if a.get("evidence") else "See report"
        rec = recs.get(aid, "Review and monitor telemetry")

        rows.append({
            "id": aid,
            "issue": title,
            "evidence_top_signal": top_ev,
            "category": "Anomaly",
            "confidence": f"{a.get('confidence', 80)}%",
            "recommended_action": rec
        })

    # Tier 2 Possible Anomalies
    for b in tier2:
        bid = b.get("id", "B?")
        title = b.get("title", "")
        top_ev = b["evidence"][0] if b.get("evidence") else "See report"
        rec = recs.get(bid, "Extend observation window")

        rows.append({
            "id": bid,
            "issue": title,
            "evidence_top_signal": top_ev,
            "category": "Possible anomaly",
            "confidence": f"{b.get('confidence', 50)}%",
            "recommended_action": rec
        })

    # Tier 3 Root Causes
    for c in tier3:
        cid = c.get("id", "C?")
        rows.append({
            "id": cid,
            "issue": f"Root cause: {c.get('title', '')}",
            "evidence_top_signal": c.get("root_cause", "")[:120] + "...",
            "category": "Root cause",
            "confidence": f"{c.get('confidence', 70)}%",
            "recommended_action": c.get("recommended_action", "")
        })

    # Tier 4 Possible Root Causes
    for d in tier4:
        did = d.get("id", "D?")
        rows.append({
            "id": did,
            "issue": f"Possible root cause: {d.get('title', '')}",
            "evidence_top_signal": d.get("hypothesis", "")[:120] + "...",
            "category": "Possible root cause",
            "confidence": f"{d.get('confidence', 40)}%",
            "recommended_action": d.get("recommended_action", "")
        })

    return rows
