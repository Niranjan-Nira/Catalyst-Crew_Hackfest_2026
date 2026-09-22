# Volume III · Chapter 3 — Reliability Data Programmatically

The Reliability Monitor's data (V1.C3.E002) is queryable — turning its visual
timeline into fleet-scale stability reporting and cross-source correlation.

---
entry_id: V3.C3.E001
title: "Win32_ReliabilityRecords and Building Stability Reports"
category: procedure
severity_for_triage: informational
applies_to: ["Windows Vista+ (RAC enabled)"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`Win32_ReliabilityRecords` exposes the same aggregated stream Reliability
Monitor charts: application failures, Windows failures, warnings, and
informational change events (installs/updates), each timestamped and
categorized. It's the cheapest single class for a "how healthy is this
machine" summary.

## Message Text & Fields
| Field | Meaning |
|---|---|
| `SourceName` | Emitting component/app |
| `EventIdentifier` | The underlying event ID |
| `ProductName` | Friendly product |
| `TimeGenerated` | When |
| `Message` | Rendered description |
| `RecordNumber` | Sequence |

## Diagnostic Procedure
1. Recent instability, categorized:
```powershell
Get-CimInstance Win32_ReliabilityRecords |
  Sort-Object TimeGenerated -Descending |
  Select-Object -First 25 TimeGenerated, SourceName, EventIdentifier, ProductName
```
2. A crude stability index — failures per day over two weeks:
```powershell
Get-CimInstance Win32_ReliabilityRecords |
  Where-Object { $_.TimeGenerated -gt (Get-Date).AddDays(-14) } |
  Group-Object { $_.TimeGenerated.Date } |
  Select-Object Name, Count | Sort-Object Name
```
3. Note: the RAC task (`\Microsoft\Windows\RAC`) must be enabled for the
   stability *index* to compute; the records themselves populate regardless.
   If Reliability Monitor shows "not enough data," the RAC task is disabled.

## Related Entries
- V1.C3.E002 — Reliability Monitor (the GUI) · V3.C3.E002 — correlation

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V3.C3.E002
title: "Correlating WER, Event Log, and Reliability Monitor Records"
category: procedure
severity_for_triage: informational
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The three crash-adjacent data sources overlap deliberately: an app crash
appears as Application Error 1000 (event log), WER 1001 + a Report.wer (WER),
and a reliability record (RAC). Correlating them by time and process turns
three partial views into one confident conclusion — and each supplies what the
others lack.

## Meaning
| Source | Uniquely provides |
|---|---|
| Event log 1000/1026 | Exact module, exception code, offset; managed exception type |
| WER 1001 + Report.wer | Bucket/signature, loaded-module list, attached dump path |
| Reliability records | The clean cross-category timeline (crashes beside installs/updates) — the "what changed" view |

The correlation key is timestamp + process name (and PID where available);
within a couple of seconds, records describing the same failure line up.

## Diagnostic Procedure
1. Build a unified timeline for one app around a failure window:
```powershell
$app = 'outlook.exe'; $t = (Get-Date).AddDays(-1)
$ev = Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000,1001,1002; StartTime=$t} -EA SilentlyContinue |
      Where-Object Message -like "*$app*" |
      Select-Object @{n='Src';e={'EventLog'}}, TimeCreated, Id, @{n='Info';e={($_.Message -split "`n")[0]}}
$rel = Get-CimInstance Win32_ReliabilityRecords |
      Where-Object { $_.TimeGenerated -gt $t -and $_.Message -like "*$app*" } |
      Select-Object @{n='Src';e={'RAC'}}, @{n='TimeCreated';e={$_.TimeGenerated}},
        @{n='Id';e={$_.EventIdentifier}}, @{n='Info';e={$_.ProductName}}
$ev + $rel | Sort-Object TimeCreated
```
2. From the WER Report Id in the 1000/1001 event, pull the matching
   `Report.wer` (V3.C1.E004) for the loaded-module list and dump — closing the
   loop from timeline to root-cause artifact.

## Related Entries
- V2.C7.E1000/E1001 · V3.C1.E002 · V3.C3.E001

## References & Attribution
- original synthesis — License: n/a
