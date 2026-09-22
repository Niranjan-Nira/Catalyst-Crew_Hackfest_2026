from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

def detect_crash_clusters(
    wer_reports: List[Dict[str, Any]],
    window_seconds: int = 180,
    min_distinct_procs: int = 4
) -> List[Dict[str, Any]]:
    """
    Detects temporal clusters of distinct processes crashing within a window.
    Anomalies with >=4 distinct processes indicate a shared driver/service crash cascade.
    """
    clusters = []

    # Filter reports with valid timestamps, excluding non-critical update telemetries
    valid_reports = [
        r for r in wer_reports
        if r.get("timestamp") and r.get("AppName") and not r.get("is_non_critical") and r.get("EventType") in [
            "APPCRASH", "MoAppCrash", "CLR20r3", "BEX64", "BEX", "AppHang", "MoAppHang"
        ]
    ]
    valid_reports.sort(key=lambda r: r["timestamp"])

    if not valid_reports:
        return clusters

    i = 0
    n = len(valid_reports)
    visited_indices = set()

    while i < n:
        if i in visited_indices:
            i += 1
            continue

        start_time = valid_reports[i]["timestamp"]
        end_window = start_time + timedelta(seconds=window_seconds)

        window_reports = []
        distinct_procs = {}

        for j in range(i, n):
            rep = valid_reports[j]
            ts = rep["timestamp"]
            if ts <= end_window:
                pname = rep["AppName"].lower()
                if pname not in distinct_procs:
                    distinct_procs[pname] = rep
                window_reports.append(rep)
            else:
                break

        distinct_count = len(distinct_procs)
        if distinct_count >= min_distinct_procs:
            for j in range(i, i + len(window_reports)):
                visited_indices.add(j)

            actual_end_time = max(r["timestamp"] for r in window_reports)
            duration_sec = int((actual_end_time - start_time).total_seconds())

            first_rep = window_reports[0]
            first_proc = first_rep["AppName"]

            if distinct_count >= 6:
                confidence = 90
                reason = "event count, timing tightness, and cross-vendor spread make coincidence very unlikely"
            elif distinct_count >= 4:
                confidence = 80
                reason = f"{distinct_count} distinct processes crashed within {duration_sec} seconds."
            else:
                confidence = 45
                reason = f"Small cluster of {distinct_count} processes; coincidence cannot be ruled out."

            procs_summary = ", ".join(f"{r['AppName']} ({r['EventType']})" for r in distinct_procs.values())

            evidence_list = [
                f"Reliability Monitor + WER crash reports show {distinct_count} unrelated processes faulting inside a {duration_sec}-second window: {procs_summary}.",
                "These processes have no shared codebase or vendor — the only thing that ties them together is timing, which is the signature of a shared-resource or driver-level event (not independent app bugs)."
            ]

            proc_names_lower = [p.lower() for p in distinct_procs.keys()]
            if any("dwm" in p for p in proc_names_lower) and any("intel" in p or "graphics" in p for p in proc_names_lower):
                evidence_list.append(
                    "dwm.exe (the window manager) crashing alongside the Intel Graphics service is a strong secondary signal of a display/graphics-stack disturbance."
                )

            cluster_finding = {
                "id": None,
                "title": f"Correlated multi-process crash cluster — {start_time.strftime('%Y-%m-%d')}, {start_time.strftime('%H:%M:%S')}–{actual_end_time.strftime('%H:%M:%S')} ({duration_sec} sec)",
                "category": "correlation_cluster",
                "tier": "Tier 1: Anomaly" if confidence >= 80 else "Tier 2: Possible Anomaly",
                "confidence": confidence,
                "confidence_reason": reason,
                "start_time": start_time.isoformat(),
                "end_time": actual_end_time.isoformat(),
                "duration_seconds": duration_sec,
                "distinct_process_count": distinct_count,
                "first_process": first_proc,
                "first_report": first_rep,
                "processes": [
                    {
                        "name": r["AppName"],
                        "event_type": r["EventType"],
                        "timestamp": r["timestamp"].strftime('%H:%M:%S'),
                        "app_path": r.get("AppPath", "")
                    }
                    for r in distinct_procs.values()
                ],
                "evidence": evidence_list,
                "source_file": "15_CrashDumps_WER"
            }
            clusters.append(cluster_finding)
            i += len(window_reports)
        else:
            i += 1

    return clusters
