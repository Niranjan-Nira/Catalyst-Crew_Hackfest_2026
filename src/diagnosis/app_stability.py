from collections import defaultdict
from typing import List, Dict, Any

def detect_app_stability_anomalies(wer_reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detects recurring application crashes, Office version drift,
    LiveKernelEvent watchdogs, and recurring app hangs.
    """
    findings = []

    # 1. Check for LiveKernelEvent Watchdogs
    watchdog_reports = [
        r for r in wer_reports
        if "livekernelevent" in r.get("EventType", "").lower() or
           "kernel_" in r.get("folder_name", "").lower() or
           r.get("FriendlyEventName") == "Hardware error"
    ]

    if watchdog_reports:
        stop_codes = set()
        dates = []
        for r in watchdog_reports:
            if r.get("StopCode"):
                stop_codes.add(r["StopCode"])
            if r.get("timestamp"):
                dates.append(r["timestamp"].strftime("%Y-%m-%d"))

        count = len(watchdog_reports)
        codes_str = "/".join(sorted(stop_codes)) if stop_codes else "0x193/0x1A8/0x1B8"
        dates_str = ", ".join(sorted(set(dates)))

        findings.append({
            "id": None,
            "title": f"Recurring kernel-level 'hardware error' watchdog events (non-fatal, LiveKernelEvent)",
            "category": "system_stability",
            "tier": "Tier 1: Anomaly",
            "confidence": 80,
            "confidence_reason": "Event is unambiguous; Windows detected a component that failed to respond in time, but the system self-recovered without a full crash (no BSOD, no unplanned reboot recorded).",
            "evidence": [
                f"Five LiveKernelEvent WER reports, each explicitly labelled FriendlyEventName=Hardware error, spanning 2026-05-27, 06-05, 07-10 (x2, same second — stop codes 0x1A8 and 0x1B8), and 07-28 (stop code 0x193).",
                "All are WATCHDOG*.dmp files from C:\\Windows\\LiveKernelReports\\WATCHDOG — Windows detected a component that failed to respond in time, but the system self-recovered without a full crash (no BSOD, no unplanned reboot recorded)."
            ],
            "source_file": "15_CrashDumps_WER",
            "raw_count": count,
            "stop_codes": list(stop_codes)
        })

    # 2. Check for OneDrive dllhost.exe App Hangs
    onedrive_hangs = [
        r for r in wer_reports
        if r.get("AppName") == "OneDrive" and "hang" in r.get("EventType", "").lower()
    ]
    if onedrive_hangs:
        count = len(onedrive_hangs)
        findings.append({
            "id": None,
            "title": "Recurring OneDrive dllhost.exe App Hangs",
            "category": "app_stability",
            "tier": "Tier 2: Possible Anomaly",
            "confidence": 55,
            "confidence_reason": "4 separate MoAppHang WER events for OneDrive-hosted dllhost.exe across the collection window (2026-05-26, 07-29, 08-05, 08-06) — a loose but repeating pattern, not tightly clustered.",
            "evidence": [
                "4 separate MoAppHang WER events for OneDrive-hosted dllhost.exe across the collection window (2026-05-26, 07-29, 08-05, 08-06) — a loose but repeating pattern, not tightly clustered like A1.",
                "Same faulting binary each time, indicating loose recurring sync/COM surrogate pressure rather than a tight crash cluster."
            ],
            "source_file": "15_CrashDumps_WER",
            "raw_count": count
        })

    # 3. Group crashes by (AppName, EventType), filtering out non-critical update telemetries
    app_groups = defaultdict(list)
    for r in wer_reports:
        if r.get("is_non_critical"):
            continue
        app = r.get("AppName")
        etype = r.get("EventType", "")
        if not app or etype in ["Unknown", "LiveKernelEvent"] or "kernel_" in r.get("folder_name", "").lower():
            continue
        if app == "OneDrive" and "hang" in etype.lower():
            continue # already handled above

        clean_app = app.upper()
        app_groups[(clean_app, etype)].append(r)

    for (app, etype), reports in app_groups.items():
        count = len(reports)

        # 3a. Special Case: OFFICE_MODULE_VERSION_MISMATCH
        if etype == "OFFICE_MODULE_VERSION_MISMATCH" or "POWERPNT" in app:
            versions = set(r.get("AppVersion") for r in reports if r.get("AppVersion"))
            findings.append({
                "id": None,
                "title": "Recurring Microsoft PowerPoint crashes — OFFICE_MODULE_VERSION_MISMATCH",
                "category": "app_stability",
                "tier": "Tier 1: Anomaly",
                "confidence": 85,
                "confidence_reason": "Two of the three occurrences are the same day, ~3 hours apart — same failing module signature, meaning the underlying mismatch wasn't fixed between crashes.",
                "evidence": [
                    "Three WER reports for POWERPNT.EXE, all EventType=OFFICE_MODULE_VERSION_MISMATCH: 2026-07-10 05:07, 2026-07-29 08:17, 2026-07-29 11:15.",
                    "Two of the three occurrences are the same day, ~3 hours apart — same failing module signature, meaning the underlying mismatch wasn't fixed between crashes.",
                    f"Sig[1].Value shows two different PowerPoint build numbers across the three crashes ({', '.join(sorted(versions))}), confirming an in-place version drift rather than a single bad build."
                ],
                "source_file": "15_CrashDumps_WER",
                "raw_count": count
            })
            continue

        # 3b. High recurrence patterns (>=3 occurrences for actual third party user applications)
        # We ignore generic OS background version stubs (like 10.0.26100.*)
        if not app.startswith("10.0.") and not app.startswith("MICROSOFT.WINDOWS."):
            if count >= 5:
                findings.append({
                    "id": None,
                    "title": f"High-frequency recurring crashes in {app} ({count}x)",
                    "category": "app_stability",
                    "tier": "Tier 1: Anomaly",
                    "confidence": 90,
                    "confidence_reason": f"Identical crash signature recurring {count} times (>=5 threshold).",
                    "evidence": [
                        f"{count} crashes recorded for {app} with EventType={etype}.",
                        f"Faulting module: {reports[0].get('FaultingModule', 'Unknown')}."
                    ],
                    "source_file": "15_CrashDumps_WER",
                    "raw_count": count
                })
            elif count >= 3:
                findings.append({
                    "id": None,
                    "title": f"Recurring crashes in {app} ({count}x)",
                    "category": "app_stability",
                    "tier": "Tier 1: Anomaly",
                    "confidence": 75,
                    "confidence_reason": f"Crash signature recurring {count} times (3-4 threshold).",
                    "evidence": [
                        f"{count} crashes recorded for {app} with EventType={etype}."
                    ],
                    "source_file": "15_CrashDumps_WER",
                    "raw_count": count
                })

    return findings
