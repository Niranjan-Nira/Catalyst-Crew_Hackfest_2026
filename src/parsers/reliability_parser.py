import csv
from pathlib import Path
from typing import List, Dict, Any, Optional

def parse_stability_index(score_file: Path) -> Dict[str, Any]:
    """
    Parse StabilityIndex_DailyScore.csv to find average stability index,
    lowest score, and any day-over-day drops greater than threshold.
    """
    result = {
        "scores": [],
        "drops": [],
        "avg_score": 0.0,
        "min_score": 10.0,
        "max_score": 1.0,
        "has_depression": False
    }

    if not score_file.exists():
        return result

    prev_score: Optional[float] = None
    prev_date: Optional[str] = None
    total_score = 0.0

    try:
        with open(score_file, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                date = row.get("Date", row.get("TimeGenerated", ""))
                val_str = row.get("SystemStabilityIndex", "")
                try:
                    score = float(val_str)
                    result["scores"].append({"date": date, "score": score})
                    total_score += score

                    if score < result["min_score"]:
                        result["min_score"] = score
                    if score > result["max_score"]:
                        result["max_score"] = score

                    if prev_score is not None:
                        drop = prev_score - score
                        if drop >= 2.0:
                            result["drops"].append({
                                "date": date,
                                "from_score": prev_score,
                                "to_score": score,
                                "drop": round(drop, 2),
                                "prev_date": prev_date
                            })

                    prev_score = score
                    prev_date = date
                except ValueError:
                    continue

        if result["scores"]:
            result["avg_score"] = round(total_score / len(result["scores"]), 2)
            # A score consistently around 5.0 is depressed
            if result["avg_score"] <= 6.0:
                result["has_depression"] = True

    except Exception:
        pass

    return result

def parse_reliability_records(records_file: Path) -> List[Dict[str, Any]]:
    """Parse ReliabilityRecords_Full.csv or ReliabilityRecords.csv."""
    records = []
    if not records_file.exists():
        return records

    try:
        with open(records_file, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    "time": row.get("TimeGenerated", row.get("Date", "")),
                    "source_name": row.get("SourceName", ""),
                    "event_identifier": row.get("EventIdentifier", ""),
                    "message": row.get("Message", "")
                })
    except Exception:
        pass

    return records
