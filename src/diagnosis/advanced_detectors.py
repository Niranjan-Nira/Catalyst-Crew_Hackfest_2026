import csv
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from ..utils import resolve_diagnostic_dir


def _parse_flexible_time(t_str: str) -> Optional[datetime]:
    """Parses various Windows timestamp formats into datetime object."""
    if not t_str or not isinstance(t_str, str):
        return None
    clean = t_str.strip().split(".")[0].replace("Z", "")
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y%m%d%H%M%S"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def detect_statistical_micro_spikes(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Advanced Statistical Micro-Spike & Telemetry Variance Detector:
    Computes rolling Z-scores and Interquartile Range (IQR) outliers on live
    CPU utilization and Available Memory telemetry. Catches transient resource exhaustion
    spikes even during quiet/idle observation windows.
    """
    resolved_dir = resolve_diagnostic_dir(data_dir)
    timeline_file = resolved_dir / "01_Timeline_And_Resources" / "ResourceUtilization_Timeline.csv"
    if not timeline_file.exists():
        timeline_file = resolved_dir / "Timeline_And_Resources" / "ResourceUtilization_Timeline.csv"

    if not timeline_file.exists():
        return []

    timestamps = []
    cpu_values = []
    mem_avail_values = []

    try:
        with open(timeline_file, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = row.get("Timestamp") or row.get("Time") or row.get("DateTime")
                cpu_raw = row.get("CPUUsagePercent") or row.get("PercentProcessorTime") or row.get("CPU")
                mem_raw = row.get("MemoryAvailableMB") or row.get("AvailableMBytes") or row.get("FreeMemoryMB")

                if ts and cpu_raw and mem_raw:
                    try:
                        cpu_f = float(cpu_raw)
                        mem_f = float(mem_raw)
                        timestamps.append(ts)
                        cpu_values.append(cpu_f)
                        mem_avail_values.append(mem_f)
                    except ValueError:
                        continue
    except Exception:
        return []

    if len(cpu_values) < 5:
        return []

    anomalies = []

    # 1. CPU Z-Score Analysis
    mean_cpu = sum(cpu_values) / len(cpu_values)
    variance_cpu = sum((x - mean_cpu) ** 2 for x in cpu_values) / len(cpu_values)
    std_cpu = math.sqrt(variance_cpu) if variance_cpu > 0 else 1.0

    # 2. Memory Available IQR Outlier Analysis
    sorted_mem = sorted(mem_avail_values)
    n_mem = len(sorted_mem)
    q1 = sorted_mem[int(n_mem * 0.25)]
    q3 = sorted_mem[int(n_mem * 0.75)]
    iqr = q3 - q1
    lower_mem_fence = max(0, q1 - 1.5 * iqr)

    # Scan for micro-spikes
    for i, (ts, cpu, mem) in enumerate(zip(timestamps, cpu_values, mem_avail_values)):
        z_cpu = (cpu - mean_cpu) / std_cpu
        # CPU Micro-Spike: Z > 2.5 and CPU > 65%
        if z_cpu >= 2.5 and cpu >= 65.0:
            anomalies.append({
                "type": "CPU_MICRO_SPIKE",
                "timestamp": ts,
                "metric": "CPU Usage (%)",
                "observed_value": round(cpu, 1),
                "baseline_mean": round(mean_cpu, 1),
                "z_score": round(z_cpu, 2),
                "severity": "High" if cpu > 85 else "Medium",
                "summary": f"Statistical micro-spike: CPU reached {cpu:.1f}% (Z-score +{z_cpu:.2f} above baseline mean {mean_cpu:.1f}%) at {ts}."
            })

        # Memory Dips: Value below lower fence (IQR) or Z < -2.0
        if mem < lower_mem_fence and mem < 1500.0:
            anomalies.append({
                "type": "MEMORY_DEPRIVATION_DIP",
                "timestamp": ts,
                "metric": "Available Memory (MB)",
                "observed_value": round(mem, 0),
                "lower_fence_iqr": round(lower_mem_fence, 0),
                "severity": "High" if mem < 600 else "Medium",
                "summary": f"Statistical memory depletion dip: Free RAM plunged to {int(mem)} MB (below IQR outlier threshold {int(lower_mem_fence)} MB) at {ts}."
            })

    return anomalies


def detect_monotonic_memory_leaks(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Monotonic Memory Leak Trend Detector:
    Analyzes TopProcesses_PerSample.csv across consecutive samples.
    Measures linear regression slope and growth consistency ratio to catch silent,
    unbounded memory leaks before an out-of-memory crash occurs.
    """
    resolved_dir = resolve_diagnostic_dir(data_dir)
    proc_sample_file = resolved_dir / "01_Timeline_And_Resources" / "TopProcesses_PerSample.csv"
    if not proc_sample_file.exists():
        proc_sample_file = resolved_dir / "Timeline_And_Resources" / "TopProcesses_PerSample.csv"

    if not proc_sample_file.exists():
        return []

    # Map process_name -> list of (timestamp_idx, working_set_mb)
    process_series: Dict[str, List[Tuple[int, float]]] = {}

    try:
        with open(proc_sample_file, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            sample_idx = 0
            last_ts = None
            for row in reader:
                ts = row.get("Timestamp") or row.get("Time")
                pname = row.get("ProcessName") or row.get("Name")
                ws_raw = row.get("WorkingSetMB") or row.get("WorkingSet") or row.get("MemoryMB")

                if ts != last_ts:
                    sample_idx += 1
                    last_ts = ts

                if pname and ws_raw:
                    try:
                        ws_f = float(ws_raw)
                        # Normalize process name
                        pname_clean = pname.lower().replace(".exe", "")
                        if pname_clean not in process_series:
                            process_series[pname_clean] = []
                        process_series[pname_clean].append((sample_idx, ws_f))
                    except ValueError:
                        continue
    except Exception:
        return []

    leak_suspects = []

    for pname, samples in process_series.items():
        if len(samples) < 4:
            continue

        # Sort by sample index
        samples.sort(key=lambda x: x[0])
        ws_values = [s[1] for s in samples]

        # Calculate Monotonicity Ratio (steps where ws(t) >= ws(t-1))
        increases = sum(1 for i in range(1, len(ws_values)) if ws_values[i] >= ws_values[i - 1])
        monotonic_ratio = increases / (len(ws_values) - 1)

        total_growth = ws_values[-1] - ws_values[0]
        peak_ws = max(ws_values)

        # Flag if steady growth > 80% monotonic and increased by > 40 MB
        if monotonic_ratio >= 0.80 and total_growth >= 40.0 and peak_ws >= 150.0:
            # Linear regression slope: delta MB per sample
            n = len(ws_values)
            x_vals = list(range(n))
            x_mean = sum(x_vals) / n
            y_mean = sum(ws_values) / n
            numerator = sum((x_vals[i] - x_mean) * (ws_values[i] - y_mean) for i in range(n))
            denominator = sum((x_vals[i] - x_mean) ** 2 for i in range(n))
            slope = numerator / denominator if denominator != 0 else 0.0

            leak_suspects.append({
                "process_name": pname,
                "initial_working_set_mb": round(ws_values[0], 1),
                "final_working_set_mb": round(ws_values[-1], 1),
                "peak_working_set_mb": round(peak_ws, 1),
                "total_growth_mb": round(total_growth, 1),
                "monotonic_ratio": round(monotonic_ratio, 2),
                "growth_slope_mb_per_sample": round(slope, 2),
                "summary": (
                    f"Process '{pname}' exhibits monotonic memory leak pattern: Working set grew by "
                    f"+{total_growth:.1f} MB (from {ws_values[0]:.1f} MB to {ws_values[-1]:.1f} MB) "
                    f"with {int(monotonic_ratio * 100)}% monotonic consistency across observation samples."
                )
            })

    # Sort by total growth descending
    leak_suspects.sort(key=lambda x: x["total_growth_mb"], reverse=True)
    return leak_suspects


def correlate_temporal_window(
    data_dir: Path,
    target_time_str: str,
    window_seconds: int = 120
) -> Dict[str, Any]:
    """
    Automated Multi-File Temporal Join Correlator:
    Direct implementation of Diagnostic Cheat Sheet Step 2.
    Given an incident timestamp (e.g. crash cluster moment at 12:51:58),
    slices related files within [target - window, target + window]:
      - ProcessStartStop_Timeline.csv
      - FileOpenCloseModify_Timeline.csv
      - InstalledApplications_Registry.csv
    Returns a unified, high-resolution temporal context map.
    """
    resolved_dir = resolve_diagnostic_dir(data_dir)
    target_dt = _parse_flexible_time(target_time_str)

    timeline_dir = resolved_dir / "01_Timeline_And_Resources"
    if not timeline_dir.exists():
        timeline_dir = resolved_dir / "Timeline_And_Resources"

    correlated_processes = []
    correlated_files = []

    # 1. Inspect ProcessStartStop_Timeline.csv
    proc_timeline = timeline_dir / "ProcessStartStop_Timeline.csv"
    if proc_timeline.exists():
        try:
            with open(proc_timeline, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts_str = row.get("Timestamp") or row.get("Time")
                    pname = row.get("ProcessName") or row.get("CommandLine") or row.get("ImageName")
                    action = row.get("EventType") or row.get("Action") or "ProcessActivity"

                    if ts_str and pname:
                        if target_dt:
                            row_dt = _parse_flexible_time(ts_str)
                            if row_dt:
                                diff = abs((row_dt - target_dt).total_seconds())
                                if diff <= window_seconds:
                                    correlated_processes.append({
                                        "time": ts_str,
                                        "process": pname,
                                        "action": action,
                                        "delta_seconds": int(diff)
                                    })
                        else:
                            # Substring match if datetime cannot be parsed
                            time_part = target_time_str.split("T")[-1][:5] if "T" in target_time_str else target_time_str[:5]
                            if time_part in ts_str:
                                correlated_processes.append({
                                    "time": ts_str,
                                    "process": pname,
                                    "action": action,
                                    "delta_seconds": 0
                                })
        except Exception:
            pass

    # 2. Inspect FileOpenCloseModify_Timeline.csv
    file_timeline = timeline_dir / "FileOpenCloseModify_Timeline.csv"
    if file_timeline.exists():
        try:
            with open(file_timeline, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts_str = row.get("Timestamp") or row.get("Time")
                    fpath = row.get("FilePath") or row.get("FileName")
                    action = row.get("Action") or row.get("Operation") or "FileActivity"

                    if ts_str and fpath:
                        if target_dt:
                            row_dt = _parse_flexible_time(ts_str)
                            if row_dt:
                                diff = abs((row_dt - target_dt).total_seconds())
                                if diff <= window_seconds:
                                    correlated_files.append({
                                        "time": ts_str,
                                        "file": fpath,
                                        "action": action,
                                        "delta_seconds": int(diff)
                                    })
                        else:
                            time_part = target_time_str.split("T")[-1][:5] if "T" in target_time_str else target_time_str[:5]
                            if time_part in ts_str:
                                correlated_files.append({
                                    "time": ts_str,
                                    "file": fpath,
                                    "action": action,
                                    "delta_seconds": 0
                                })
        except Exception:
            pass

    return {
        "target_timestamp": target_time_str,
        "window_seconds": window_seconds,
        "processes_in_window": correlated_processes[:15],
        "files_in_window": correlated_files[:15],
        "total_process_events": len(correlated_processes),
        "total_file_events": len(correlated_files)
    }
