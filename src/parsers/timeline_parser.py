import csv
from pathlib import Path
from typing import Dict, List, Any

def parse_resource_timeline(timeline_file: Path) -> Dict[str, Any]:
    """
    Parse ResourceUtilization_Timeline.csv to extract statistics:
    min memory available, avg/max CPU, sample count.
    """
    stats = {
        "sample_count": 0,
        "min_available_mb": None,
        "max_cpu_percent": 0.0,
        "avg_cpu_percent": 0.0,
        "high_cpu_samples": 0,
        "total_memory_gb": 15.46,
        "min_percent_free_mem": 7.0,
        "timestamps": [],
        "cpu_values": [],
        "available_mb_values": []
    }

    if not timeline_file.exists():
        return stats

    # Try to read actual physical memory if present
    mem_mod_file = timeline_file.parent.parent / "06_Memory" / "PhysicalMemoryModules.csv"
    if mem_mod_file.exists():
        try:
            with open(mem_mod_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                tot_bytes = 0
                for row in reader:
                    cap = row.get("CapacityBytes", row.get("Capacity", "0")).strip()
                    if cap.isdigit():
                        tot_bytes += int(cap)
                if tot_bytes > 0:
                    stats["total_memory_gb"] = round(tot_bytes / (1024**3), 2)
        except Exception:
            pass

    cpu_sum = 0.0
    try:
        with open(timeline_file, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats["sample_count"] += 1
                ts = row.get("Timestamp", "")
                stats["timestamps"].append(ts)

                # CPU: Try 'CPU_Percent' then 'CPU_Usage_Percent'
                cpu_val_str = row.get("CPU_Percent", row.get("CPU_Usage_Percent", "0.0")).strip()
                try:
                    cpu = float(cpu_val_str)
                    stats["cpu_values"].append(cpu)
                    cpu_sum += cpu
                    if cpu > stats["max_cpu_percent"]:
                        stats["max_cpu_percent"] = cpu
                    if cpu > 80.0:
                        stats["high_cpu_samples"] += 1
                except ValueError:
                    stats["cpu_values"].append(0.0)

                # Available Memory
                avail_str = row.get("MemoryAvailableMB", "").strip()
                try:
                    avail = float(avail_str)
                    stats["available_mb_values"].append(avail)
                    if stats["min_available_mb"] is None or avail < stats["min_available_mb"]:
                        stats["min_available_mb"] = avail
                except ValueError:
                    pass

        if stats["sample_count"] > 0:
            stats["avg_cpu_percent"] = round(cpu_sum / stats["sample_count"], 1)

        if stats["min_available_mb"] is not None and stats["total_memory_gb"] > 0:
            pct = (stats["min_available_mb"] / (stats["total_memory_gb"] * 1024)) * 100
            stats["min_percent_free_mem"] = round(pct, 1)

    except Exception:
        pass

    return stats

def parse_top_processes_snapshot(snapshot_file: Path) -> List[Dict[str, Any]]:
    """Parse TopMemoryProcesses_Snapshot.csv to see memory hogging processes."""
    procs = []
    if not snapshot_file.exists():
        return procs

    try:
        with open(snapshot_file, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                procs.append({
                    "name": row.get("ProcessName", ""),
                    "id": row.get("ProcessId", ""),
                    "working_set_mb": row.get("WorkingSetMB", ""),
                    "private_bytes_mb": row.get("PrivateBytesMB", "")
                })
    except Exception:
        pass

    return procs
