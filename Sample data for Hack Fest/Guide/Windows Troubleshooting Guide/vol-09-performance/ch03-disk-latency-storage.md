# Volume IX · Chapter 3 — Disk Latency and Storage Performance

The most misread performance metric in Windows is "Disk %". This chapter is
about measuring storage the way that actually tells you if the disk is the
bottleneck — latency, not utilization — and attributing the load.

---
entry_id: V9.C3.E001
title: "Measuring Disk Latency the Right Way"
category: procedure
severity_for_triage: high
applies_to: ["Windows 8+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Task Manager's "Disk 100%" and PerfMon's `% Disk Time` are misleading — they
can read 100% under trivial load and say nothing about whether I/O is *slow*.
The truth metric is **latency**: `Avg. Disk sec/Read` and `Avg. Disk
sec/Write`, in milliseconds. That's what users feel as "the machine is
sluggish."

## Diagnostic Procedure
1. Measure latency (the numbers that matter):
```powershell
Get-Counter -Counter '\LogicalDisk(*)\Avg. Disk sec/Read',
  '\LogicalDisk(*)\Avg. Disk sec/Write',
  '\LogicalDisk(*)\Current Disk Queue Length' -SampleInterval 2 -MaxSamples 15
```
2. Interpret (rough client thresholds):
   | Avg sec/Read or Write | Verdict |
   |---|---|
   | < 0.010 (10 ms) | Healthy (SSD often < 1 ms) |
   | 0.010–0.025 | Acceptable under load |
   | 0.025–0.050 | Sluggish; investigate |
   | > 0.050 sustained | Storage is the bottleneck |
   HDDs run higher than SSDs; a sustained multi-hundred-ms latency on any drive
   is a problem regardless of media.
3. Correlate high latency with the storage *event* layer (V2.C4): 129 resets,
   153 retries, or disk 7/11 mean the latency is a failing-hardware symptom,
   not just load.
4. Health counters (SSD wear/errors, V7.C1.E005):
```powershell
Get-PhysicalDisk | Get-StorageReliabilityCounter |
  Select-Object DeviceId, Wear, ReadErrorsUncorrected, Temperature
```

## Related Entries
- V2.C4.* — storage events · V9.C3.E002 — what's causing the I/O

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V9.C3.E002
title: "What's Hitting the Disk: Attribution and Antivirus"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Once latency confirms the disk is busy, the next question is *who* and *on
which files*. Two tools answer it live without a trace: Resource Monitor's Disk
tab (per-file I/O by process) and the storage-filter view for real-time
scanning overhead — because antivirus real-time scanning is, in practice, the
single most common cause of disk-bound slowness on managed clients.

## Diagnostic Procedure
1. Per-process, per-file I/O right now:
```
resmon  →  Disk tab  →  sort by Total (B/sec); the "File" column names the
exact path each process is hammering
```
2. Programmatic top I/O (PS7 has no native per-process disk cmdlet; use the
   process I/O counters as a proxy):
```powershell
Get-Process | Sort-Object { $_.IO_ReadBytes + $_.IO_WriteBytes } -Descending -EA SilentlyContinue |
  Select-Object -First 10 Name, Id,
    @{n='IO_MB';e={[int](($_.'IO_ReadBytes'+$_.'IO_WriteBytes')/1MB)}} -EA SilentlyContinue
```
3. **Antivirus overhead** — measure what real-time scanning costs by path
   (Defender; V6.C2.E001):
```powershell
New-MpPerformanceRecording -RecordTo C:\Diag\av.etl   # reproduce load, Ctrl-C
Get-MpPerformanceReport -Path C:\Diag\av.etl -TopFiles 20 -TopPaths 20 -TopProcesses 10
```
   This names the exact files/paths/processes real-time scanning is spending
   time on — the evidence for a *targeted* exclusion (build output, database
   files, dev toolchains), which is the fix, not disabling protection.
4. Filter-driver stack review (backup/dedup/EDR filters also add I/O latency):
```cmd
fltmc filters
```

## Related Entries
- V6.C2.E001 — Defender exclusions · V1.C3.E004 — Resource Monitor · V1.C2.E005 — filter drivers

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V9.C3.E003
title: "Memory Pressure and the Paging Connection"
category: concept
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Disk and memory performance are entangled: when physical RAM runs short,
Windows pages to disk, and *that* paging shows up as disk latency and "slow
disk" complaints — when the real problem is memory. The tell is high **hard
fault** rates (page faults served from disk) alongside the disk latency.

## Diagnostic Procedure
1. Check whether the disk load is actually paging:
```powershell
Get-Counter '\Memory\Pages/sec','\Memory\Page Reads/sec',
  '\Memory\Available MBytes','\Process(*)\Working Set - Private' -MaxSamples 10 -SampleInterval 2
```
   Sustained high `Page Reads/sec` with low `Available MBytes` = memory
   pressure driving disk I/O; fix the memory hog (V9.C2.E001), not the disk.
2. Resource Monitor's Memory tab shows **Hard Faults/sec** per process live —
   the process with high hard faults is the one being starved.
3. Confirm the page file isn't on a failing/slow disk (that compounds the
   problem — ties to disk 51 paging errors, V2.C4.E051):
```powershell
Get-CimInstance Win32_PageFileUsage | Select-Object Name, AllocatedBaseSize, CurrentUsage
```
4. Distinguish the two fixes: genuine memory shortage → add RAM / fix the leak;
   healthy memory but slow page device → the storage problem is primary.

## Related Entries
- V9.C2.E001 — the memory side · V2.C4.E051 — paging errors · V9.C3.E001 — latency

## References & Attribution
- original synthesis — License: n/a
