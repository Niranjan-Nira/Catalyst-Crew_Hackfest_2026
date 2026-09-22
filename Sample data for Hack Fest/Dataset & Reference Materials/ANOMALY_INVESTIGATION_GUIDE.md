# Anomaly Investigation Guide — How to Actually Do This
---

## 1. Where do I check first, and what does that lead to?

Think of this as a **funnel with branches**, not a checklist you read
top-to-bottom. You start at 2 files, and each one either clears a category
(nothing to see, move on) or hands you a **child lead** — a specific
timestamp, process name, or device name — that tells you exactly which
folder to open next.

```
START
  │
  ├── _StatusReport/StatusReport.txt
  │     Tells you what data you can trust. A "Failed" phase means
  │     "don't conclude anything from that folder being empty."
  │
  ├── 09_ReliabilityMonitor/StabilityIndex_DailyScore.csv
  │     LEAD: a sharp score drop on a specific date
  │     → child lead: "check what happened around <that date>"
  │
  ▼
Does a lead exist (a date, a device name, a process name)?
  │
  ├── NO lead yet → check the "presence = signal" files:
  │     04_HardwareDevices/DevicesWithConfigManagerErrors.csv
  │     06_Memory/WHEA_HardwareMemoryErrors.csv
  │     07_CPU/CPU_WHEA_Errors.csv, CPU_ThrottlingEvents.csv
  │     16_Services_Processes/AppCrashHang_PersistentHistory.csv
  │     Any non-empty file here IS a lead → go to the branch below
  │
  └── YES, a lead exists → follow the CHILD ITEM the lead names:
        │
        ├── Lead is a DATE → go to 02_EventLogs/CSV_Readable/*.csv,
        │     filter every log to that date, see what fired together
        │
        ├── Lead is a PROCESS NAME → go to 15_CrashDumps_WER/,
        │     find every crash folder for that process name,
        │     decode Report.wer (see Section 4), check if it repeats
        │
        ├── Lead is a DEVICE NAME → go to
        │     08_SystemInfo/AllDrivers_VersionDate.csv,
        │     find that device's driver version/install date
        │
        └── Lead is "nothing found anywhere" → go to
              01_Timeline_And_Resources/ (the live 30-min capture)
              — this is your only real-time data; a chronic issue that
              doesn't show up in history might still show up live
```

**The point:** every file you open should either close a question or open a
more specific one. If you're opening a file with no specific question in
mind, you're browsing, not investigating — go back one step and find the
lead that should have sent you there.

---

## 2. What are the categories of anomaly, and how do they connect?

There are **9 categories** used in the labeled dataset. They are not
independent — several connect to each other through shared evidence.

| Category | What it covers | Typically found in |
|---|---|---|
| `disk` | Free space, physical health, SMART prediction, IO retries | `05_Disk/`, `DiskHealth/` |
| `memory_hardware` | Hardware-level RAM error signals (WHEA) | `06_Memory/` |
| `cpu_hardware` | CPU hardware errors, throttling, temperature | `07_CPU/`, `Timeline_Thermal_Power_Fan/` |
| `driver_device` | Device Manager errors, degraded/failed hardware | `04_HardwareDevices/`, `Drivers/` |
| `app_stability` | Application crashes/hangs, single or recurring | `15_CrashDumps_WER/`, `16_Services_Processes/` |
| `correlation_cluster` | Multiple unrelated processes failing together | Built from `15_CrashDumps_WER/` (all crashes, not filtered by app) |
| `reliability_onset` | A sharp day-over-day stability score drop | `09_ReliabilityMonitor/` |
| `system_stability` | Unexpected shutdowns/reboots | `BootShutdownHistory/` (Device-2-style schema) |
| `update_failure` | Failed Windows Update/app installs | `03_WindowsUpdates/`, `ReliabilityHistory/` |

### How they connect (this is the important part)

```
reliability_onset  ──(tells you WHEN)──►  everything else
                                            (use the date to filter)

app_stability (single app, repeating)  ──(if the SAME app appears
                                            in a driver_device or
                                            memory_hardware finding)──►
                                            possible shared cause

app_stability (many DIFFERENT apps,
    same few minutes)  ──IS──►  correlation_cluster
    (this is a special case of app_stability, not a separate data source —
     you build it by looking at ALL crashes together instead of one app
     at a time)

driver_device  ──(if the failing device is storage/memory-related)──►
                    may explain a disk or memory_hardware finding too

update_failure  ──(if it recurs across MULTIPLE devices)──►
                    becomes a fleet-wide possible_root_cause,
                    not a single-device app_stability issue
```

`reliability_onset` is special: it never stands alone as a root cause. Its
only job is to tell you *which date* to go filter every other category by.

`correlation_cluster` is also special: it isn't a new data source, it's a
different *lens* on the same WER crash data you'd use for `app_stability` —
instead of asking "does this ONE app crash a lot," you ask "did MANY
different apps crash at the SAME time."

---

## 3. If I call something an anomaly, where do I go to verify it, and what part of the file?

For each category, here is exactly what to open and which field to look at.

| Category | File to open | Field to check | What counts as confirmation |
|---|---|---|---|
| `disk` (free space) | `05_Disk/Drives_SizeFreeSpace.csv` | `PercentFree` column | Numeric value below your threshold — no interpretation needed |
| `disk` (SMART) | `DiskHealth/SMART_FailurePredictStatus.csv` | `PredictFailure` column | Literal string `True` |
| `memory_hardware` | `06_Memory/WHEA_HardwareMemoryErrors.csv` | `LevelDisplayName` column | Must say `Error` or `Critical` — `Information` is NOT the same thing (see Section 5) |
| `driver_device` | `04_HardwareDevices/DevicesWithConfigManagerErrors.csv` | `ConfigManagerErrorCode` column | Any non-blank code in this specific file (not `ProblemDevices_ONLY.csv`, which is mostly noise) |
| `app_stability` | `15_CrashDumps_WER/<folder>/Report.wer` | `EventType=` line | Same `EventType` + same process appearing 3+ times = confirmed pattern |
| `correlation_cluster` | Same `Report.wer` files, but sorted by `EventTime=` across ALL folders | `EventTime=` field, converted (Section 5) | 4+ DIFFERENT process names within a ~180 second window |
| `reliability_onset` | `09_ReliabilityMonitor/StabilityIndex_DailyScore.csv` | `SystemStabilityIndex` column | A drop of more than ~2-3 points from the previous day |
| `system_stability` | `BootShutdownHistory/BootShutdownEvents_KernelPower.csv` | `Id` column | Literal value `41` |

**Reference for what these fields mean, generally:** Microsoft's own
documentation of Windows Error Reporting bucket types and Event IDs is the
authoritative source — search `<the exact EventType or Id value>` on
[Microsoft Learn](https://learn.microsoft.com) or
[eventid.net](https://eventid.net) when you hit a code not covered here. This
guide only documents the specific codes that actually appeared in the real
device data — see Section 5 for the full list with real examples.

---

## 4. The message text is huge — which part do I actually read?

`Report.wer` files and Windows event `Message` fields can be a wall of text.
You almost never need to read the whole thing. Here's the triage:

### For `Report.wer` files
The file is a flat `Key=Value` list (hundreds of lines). You need **4 lines**,
not the whole file:
```
EventType=APPCRASH                    <- read this FIRST, always
EventTime=134305807182322575          <- convert this (Section 5)
Sig[0].Value=spksvc.exe               <- the actual crashing app/module
Sig[1].Value=3.0.8.0                  <- Version
```
Everything else in the file (`OSVersion=`, `LCID=`, `ReportIdentifier=`, the
dozens of other `Sig[n]` fields) is metadata you only need for deep forensic
work, not for the anomaly/root-cause pass. Grep for just these 4 keys and
move on.

### For Windows event log `Message` fields (the multi-line ones)
Real example (Application log, Event ID 1000):
```
Faulting application name: MsMpEng.exe, version: 4.18.26070.9, time stamp: 0x9a78fc05
Faulting module name: mpengine.dll, version: 1.1.26070.7, time stamp: 0xa09e75a9
Exception code: 0xc0000005
Fault offset: 0x000000000092e48b
```
You need exactly **2 of these 4 lines**:
- **`Faulting application name:`** — which program crashed (the thing you'll
  group/count for recurrence).
- **`Faulting module name:`** — which specific file inside that program
  actually broke. If this is a foreign vendor's file instead of the crashing
  app's own file, that's a real clue (see the Device-1 cluster investigation
  — checking this field for `dwm.exe`'s crash was how we ruled out code
  injection).

`Exception code:` and `Fault offset:` are only needed if you're doing deep
binary-level forensics (which this hackathon doesn't require) — you can
safely skip them on a first pass.

### The rule of thumb
**Read the first line, and any line starting with "Faulting". Skip the rest
unless your first pass didn't answer the question.**

---

## 5. What do the codes and timestamps actually mean?

### Timestamps — 2 different formats you'll hit

1. **Normal date strings** (`TimeCreated`, `TimeGenerated` columns in CSVs) —
   these are already human-readable, just inconsistent in format across
   files (`24-08-2026 13:26:09` vs `8/4/2026 7:29:01 AM`). Just parse with a
   flexible date parser (`pandas.to_datetime` handles most of these
   automatically).

2. **`EventTime=` inside `Report.wer` files** — this is a **Windows
   FILETIME**, a raw integer, not a normal date at all. You must convert it:
   ```python
   from datetime import datetime, timedelta
   def filetime_to_dt(ft):
       return datetime(1601, 1, 1) + timedelta(microseconds=int(ft) / 10)

   # Real example from this dataset:
   # EventTime=134305807182322575
   # -> 2026-08-07 12:51:58.232258
   ```

### Event IDs / codes actually seen in this data, and what they mean

| Code | Where seen | Meaning | Confidence in this meaning |
|---|---|---|---|
| `Id=1000`, Application log, Source "Application Error" | `AppCrashHang_PersistentHistory.csv` | A user-mode application crashed. The `Message` names the faulting app/module. This is Microsoft's own documented event ID for this exact scenario. | High — this is a standard, widely-documented Windows Event ID |
| `Id=41`, System log, Source "Microsoft-Windows-Kernel-Power", Level Critical | `BootShutdownEvents_KernelPower.csv` | "The system has rebooted without cleanly shutting down first" (this is the literal message text in the real data). Means a hang, crash, or power loss forced a hard reset. | High — this is a standard, widely-documented Windows Event ID |
| `Id=153`, Source "disk", Level Warning | `DiskRelatedEvents.csv` | "The IO operation ... was retried" (literal message text). The disk/controller failed a read/write and Windows retried it. Occasional occurrences are normal; high volume suggests a struggling drive. | High — this is a standard, widely-documented Windows Event ID |
| `Id=3`, Source "Microsoft-Windows-WHEA-Logger", Level **Information** | `WHEA_HardwareMemoryErrors.csv` (Devices 4, 6) | Literal message: "A hardware event has occurred. An informational record..." **Note the Level is Information, not Error** — Windows itself is not classifying this as a confirmed fault, just logging that a hardware-level record exists. This is why these rows are labeled `possible_anomaly`, not `anomaly`, in the dataset. | Medium — the message is self-explanatory about severity, but WHEA's internal sub-codes are not fully documented in this pass; treat as "hardware subsystem logged something," not "confirmed failure" |
| `EventType=APPCRASH`, `AppHang`, `OFFICE_MODULE_VERSION_MISMATCH`, etc. (WER bucket types) | `Report.wer` files | Microsoft's own crash classification bucket. `APPCRASH` = the app terminated unexpectedly; `AppHang` = the app stopped responding; `OFFICE_MODULE_VERSION_MISMATCH` = two Office components are at different versions. | High — these are Microsoft's own documented WER bucket names |
| `ConfigManagerErrorCode` values like `CM_PROB_FAILED_POST_START`, `CM_PROB_FAILED_START` | `DevicesWithConfigManagerErrors.csv` | The device driver failed during or after initialization. These are Windows' own named device-manager error constants. | High — these are documented Windows API constants |

**Honesty note:** the table above only documents codes that actually
appeared in the 5 real devices. If you encounter a code not listed here
(and you will — Windows has hundreds), the reliable way to look it up is
Microsoft Learn's own event/error documentation, not guessing from the
number alone.

---

## 6. There's so much in the logs — what's actually important?

Out of everything a full collection captures, this is the priority order:

**Tier 1 — always check these regardless of what you're investigating:**
- `_StatusReport` (or equivalent) — what can you trust
- Reliability/stability score — when did things start going wrong

**Tier 2 — the "presence = signal" files (empty is good news, non-empty is your lead):**
- Device Manager config errors
- WHEA memory/CPU errors (but check the severity level — Section 5)
- Persistent app crash/hang history

**Tier 3 — go here only once Tier 1/2 gave you a specific lead:**
- The full WER crash dump archive (huge — don't browse it, search it)
- Raw event logs (huge — filter by date/provider, don't read linearly)
- Installed apps / driver versions (only to check timing against a lead you already have)

**Ignore unless something specifically points you there:**
- Startup apps, network throughput samples, battery reports — these are
  context for a *specific* hypothesis (e.g. "is this a network issue"), not
  places to start a general investigation.

**The single highest-value habit:** don't read a file linearly. Every file
in this dataset is small enough to filter/group/count programmatically
(pandas `value_counts()`, `groupby()`) — use that instead of scrolling.
