from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Dict, List, Optional, Any

def filetime_to_datetime(filetime_val: Any) -> Optional[datetime]:
    """Convert Windows 64-bit FILETIME integer to Python datetime."""
    try:
        ft = int(filetime_val)
        return datetime(1601, 1, 1) + timedelta(microseconds=ft / 10)
    except Exception:
        return None

def parse_single_wer(wer_path: Path) -> Dict[str, Any]:
    """Parse a single UTF-16LE Report.wer file."""
    folder_name = wer_path.parent.name
    is_non_critical = folder_name.startswith("NonCritical_")

    info: Dict[str, Any] = {
        "file_path": str(wer_path),
        "folder_name": folder_name,
        "is_non_critical": is_non_critical,
        "EventType": "Unknown",
        "EventTime_raw": None,
        "timestamp": None,
        "AppPath": None,
        "FriendlyEventName": None,
        "AppName": None,
        "AppVersion": None,
        "FaultingModule": None,
        "ModuleVersion": None,
        "ExceptionCode": None,
        "StopCode": None,
        "raw_signals": {}
    }

    try:
        content = wer_path.read_text(encoding="utf-16le", errors="ignore")
    except Exception:
        try:
            content = wer_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return info

    for line in content.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()

        if key == "EventType":
            info["EventType"] = val
        elif key == "EventTime":
            info["EventTime_raw"] = val
            info["timestamp"] = filetime_to_datetime(val)
        elif key == "AppPath":
            info["AppPath"] = val
        elif key == "FriendlyEventName":
            info["FriendlyEventName"] = val
        elif key.startswith("Sig[") or key.startswith("DynamicSig["):
            info["raw_signals"][key] = val

    sig0 = info["raw_signals"].get("Sig[0].Value")
    sig1 = info["raw_signals"].get("Sig[1].Value")
    sig2 = info["raw_signals"].get("Sig[2].Value")
    sig3 = info["raw_signals"].get("Sig[3].Value")

    # Stop code extraction for LiveKernelEvent
    folder_lower = folder_name.lower()
    if "kernel_" in folder_lower:
        match = re.search(r"kernel_([0-9a-fA-F]+)_", folder_name)
        if match:
            info["StopCode"] = f"0x{match.group(1).upper()}"
    elif "livekernelevent" in info["EventType"].lower():
        if sig0 and sig0.startswith("0x"):
            info["StopCode"] = sig0

    # App Name Resolution
    # Special handling for UWP/Modern App Hangs (e.g. OneDriveSync)
    if "onedri" in folder_lower or (sig0 and "onedrive" in sig0.lower()):
        info["AppName"] = "OneDrive"
    elif sig0 and ("." in sig0 or len(sig0) < 40) and not sig0.startswith("praid:"):
        info["AppName"] = sig0
    elif info["AppPath"]:
        info["AppName"] = Path(info["AppPath"]).name
    elif sig1 and not sig1.startswith("praid:"):
        info["AppName"] = sig1
    else:
        parts = folder_name.split("_")
        if len(parts) > 1:
            info["AppName"] = parts[1]

    info["AppVersion"] = sig1
    info["FaultingModule"] = sig2 or sig0
    info["ModuleVersion"] = sig3

    return info

def parse_wer_directory(wer_dir: Path) -> List[Dict[str, Any]]:
    """Recursively discover and parse all Report.wer files in the given directory."""
    reports = []
    if not wer_dir.exists():
        return reports

    for wer_file in wer_dir.rglob("Report.wer"):
        report = parse_single_wer(wer_file)
        reports.append(report)

    reports.sort(key=lambda r: r["timestamp"] or datetime.min)
    return reports
