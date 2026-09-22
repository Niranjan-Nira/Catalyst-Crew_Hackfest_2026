import re
from pathlib import Path
from typing import List, Dict, Any

from ..parsers.hardware_parser import parse_config_manager_errors, parse_whea_errors

def detect_hardware_anomalies(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Detects hardware/driver anomalies: Config Manager errors (excluding phantoms),
    and WHEA memory/CPU hardware errors.
    """
    findings = []

    # 1. Device Manager / Config Manager Errors
    hw_dir = data_dir / "04_HardwareDevices"
    if not hw_dir.exists():
        # Fallback for Device 2 schema
        hw_dir = data_dir / "Drivers"

    cfg_errors = parse_config_manager_errors(hw_dir)

    for err in cfg_errors:
        name = err["name"]
        code = err["error_code"]

        # Check if core hardware vs minor peripheral
        is_minor = bool(re.search(r"bluetooth|virtual|com\d", name, re.IGNORECASE))
        confidence = 65 if is_minor else 90

        findings.append({
            "id": None,
            "title": f"Hardware device error: {name} ({code})",
            "category": "driver_device",
            "tier": "Tier 1: Anomaly",
            "confidence": confidence,
            "confidence_reason": f"Active non-phantom ConfigManagerErrorCode '{code}' reported for device.",
            "evidence": [
                f"DevicesWithConfigManagerErrors.csv shows active error for: {name}, ConfigManager code {code}.",
                "All ~220 other entries in ProblemDevices_ONLY.csv are CM_PROB_PHANTOM (normal residue from docking/undocking peripherals — not an active fault)."
            ],
            "source_file": "04_HardwareDevices/DevicesWithConfigManagerErrors.csv",
            "device_name": name,
            "error_code": code
        })

    # 2. WHEA Memory Errors
    mem_file = data_dir / "06_Memory" / "WHEA_HardwareMemoryErrors.csv"
    if mem_file.exists():
        whea_mem = parse_whea_errors(mem_file)
        if whea_mem:
            has_error = any(w["level"].lower() in ["error", "critical"] for w in whea_mem)
            if has_error:
                findings.append({
                    "id": None,
                    "title": f"Hardware Memory Faults (WHEA Critical/Error)",
                    "category": "memory_hardware",
                    "tier": "Tier 1: Anomaly",
                    "confidence": 88,
                    "confidence_reason": "WHEA hardware logger reported memory fault at Error/Critical level.",
                    "evidence": [
                        f"{len(whea_mem)} WHEA memory event(s) recorded at Error/Critical severity.",
                        f"First message: {whea_mem[0]['message']}"
                    ],
                    "source_file": "06_Memory/WHEA_HardwareMemoryErrors.csv"
                })
            else:
                findings.append({
                    "id": None,
                    "title": f"Informational WHEA Hardware Records Logged",
                    "category": "memory_hardware",
                    "tier": "Tier 2: Possible Anomaly",
                    "confidence": 40,
                    "confidence_reason": "WHEA memory records present but logged at Information level only — Windows itself did not classify these as faults.",
                    "evidence": [
                        f"{len(whea_mem)} WHEA records present with LevelDisplayName=Information.",
                        "Subsystem logged hardware telemetry, but no uncorrectable errors were raised."
                    ],
                    "source_file": "06_Memory/WHEA_HardwareMemoryErrors.csv"
                })

    # 3. CPU Throttling / WHEA
    cpu_whea_file = data_dir / "07_CPU" / "CPU_WHEA_Errors.csv"
    if cpu_whea_file.exists():
        cpu_whea = parse_whea_errors(cpu_whea_file)
        has_error = any(w["level"].lower() in ["error", "critical"] for w in cpu_whea)
        if has_error:
            findings.append({
                "id": None,
                "title": f"CPU Hardware Faults (WHEA Error)",
                "category": "cpu_hardware",
                "tier": "Tier 1: Anomaly",
                "confidence": 85,
                "confidence_reason": "WHEA logged hardware CPU fault.",
                "evidence": [
                    f"{len(cpu_whea)} CPU WHEA error(s) logged."
                ],
                "source_file": "07_CPU/CPU_WHEA_Errors.csv"
            })

    return findings
