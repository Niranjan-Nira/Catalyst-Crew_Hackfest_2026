import csv
from pathlib import Path
from typing import List, Dict, Any, Optional

def parse_display_external_errors(event_dir: Path) -> Dict[str, Any]:
    """
    Check for chronic Intel Graphics external-display error (Event ID 10).
    Searches in CSV_Readable for Intel-Gfx-Display-External*.csv.
    """
    res = {
        "found": False,
        "count": 0,
        "event_id": "10",
        "provider": "Intel-Gfx-Display-External",
        "file_name": "",
        "first_timestamp": None,
        "last_timestamp": None
    }

    if not event_dir.exists():
        return res

    csv_files = list(event_dir.rglob("*Intel-Gfx-Display-External*.csv"))
    if not csv_files:
        return res

    target_file = csv_files[0]
    res["file_name"] = target_file.name

    try:
        with open(target_file, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            timestamps = []
            for row in reader:
                id_val = str(row.get("Id", "")).strip()
                if id_val == "10":
                    res["count"] += 1
                    ts = row.get("TimeCreated", "").strip()
                    if ts:
                        timestamps.append(ts)

            if res["count"] > 0:
                res["found"] = True
                if timestamps:
                    res["last_timestamp"] = timestamps[0]
                    res["first_timestamp"] = timestamps[-1]
    except Exception:
        pass

    return res

def parse_kernel_power_events(event_dir: Path) -> List[Dict[str, Any]]:
    """
    Parse specifically for Event ID 41 (Kernel-Power Critical:
    'The system has rebooted without cleanly shutting down first').
    """
    events = []
    candidates = list(event_dir.rglob("*BootShutdownEvents_KernelPower*.csv")) + list(event_dir.rglob("*System*.csv"))
    for candidate in candidates:
        try:
            with open(candidate, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    id_val = str(row.get("Id", "")).strip()
                    provider = str(row.get("ProviderName", "")).lower()
                    msg = str(row.get("Message", ""))
                    level = str(row.get("LevelDisplayName", "")).lower()

                    if id_val == "41" and ("kernel-power" in provider or "rebooted without cleanly" in msg or level == "critical"):
                        events.append({
                            "timestamp": row.get("TimeCreated", ""),
                            "id": "41",
                            "message": msg,
                            "source_file": candidate.name
                        })
        except Exception:
            pass
    return events

def parse_disk_io_retries(event_dir: Path) -> Dict[str, Any]:
    """Parse DiskRelatedEvents.csv or System.csv for Event ID 153 (IO operation retried)."""
    res = {"count": 0, "events": [], "source_file": ""}
    candidates = list(event_dir.rglob("*DiskRelatedEvents*.csv")) + list(event_dir.rglob("*System*.csv"))
    for candidate in candidates:
        try:
            with open(candidate, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    id_val = str(row.get("Id", "")).strip()
                    if id_val == "153":
                        res["count"] += 1
                        res["source_file"] = candidate.name
                        if len(res["events"]) < 5:
                            res["events"].append({
                                "timestamp": row.get("TimeCreated", ""),
                                "message": row.get("Message", "")
                            })
        except Exception:
            pass
        if res["count"] > 0:
            break
    return res
