import csv
from pathlib import Path
from typing import List, Dict, Any

def parse_config_manager_errors(device_dir: Path) -> List[Dict[str, Any]]:
    """
    Parse DevicesWithConfigManagerErrors.csv and ProblemDevices_ONLY.csv.
    High-signal: ignores CM_PROB_PHANTOM (unplugged peripherals).
    """
    errors = []
    cfg_file = device_dir / "DevicesWithConfigManagerErrors.csv"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("ConfigManagerErrorCode", "").strip()
                    if code and code != "CM_PROB_PHANTOM" and code != "0":
                        errors.append({
                            "source": "DevicesWithConfigManagerErrors.csv",
                            "name": row.get("Name", "Unknown Device"),
                            "device_id": row.get("DeviceID", ""),
                            "error_code": code,
                            "is_phantom": False
                        })
        except Exception as e:
            pass

    # If DevicesWithConfigManagerErrors was empty or absent, check ProblemDevices_ONLY.csv
    # but strictly filter out CM_PROB_PHANTOM
    prob_file = device_dir / "ProblemDevices_ONLY.csv"
    if prob_file.exists():
        try:
            with open(prob_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("ConfigManagerErrorCode", "").strip()
                    status = row.get("Status", "").strip()
                    if code == "CM_PROB_PHANTOM":
                        continue
                    if code and code != "0":
                        # avoid duplicate device_id
                        if not any(e["device_id"] == row.get("DeviceID") for e in errors):
                            errors.append({
                                "source": "ProblemDevices_ONLY.csv",
                                "name": row.get("Name", "Unknown Device"),
                                "device_id": row.get("DeviceID", ""),
                                "error_code": code,
                                "status": status,
                                "is_phantom": False
                            })
        except Exception:
            pass

    return errors

def parse_whea_errors(file_path: Path) -> List[Dict[str, Any]]:
    """Parse WHEA memory or CPU error CSV, distinguishing Error/Critical from Information."""
    events = []
    if not file_path.exists():
        return events

    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                level = row.get("LevelDisplayName", "").strip()
                if not level and "Level" in row:
                    level = row.get("Level", "").strip()
                events.append({
                    "timestamp": row.get("TimeCreated", ""),
                    "id": row.get("Id", ""),
                    "level": level,
                    "message": row.get("Message", ""),
                    "source_file": file_path.name
                })
    except Exception:
        pass

    return events
