# Volume I · Chapter 1 — The Troubleshooting Discipline

---
entry_id: V1.C1.E001
title: "The Scientific Method Applied to Windows Failures"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
 
status: draft
---

## Overview
Effective Windows troubleshooting is hypothesis-driven: observe precisely,
form a falsifiable hypothesis about the mechanism, design the cheapest test
that could disprove it, and let the evidence — not the first plausible story —
decide. The alternative, "try fixes until something works," occasionally
succeeds and never teaches, and on fleets it multiplies risk by the machine
count.

## Historical / Technical Context
The discipline matters more on Windows than most platforms because the system
narrates itself so thoroughly: event logs, WER reports, CBS transactions,
ETW traces. Most failures have already written their own explanation
somewhere; the craft is knowing where the narration lives (this encyclopedia's
purpose) and reading it before theorizing.

## Meaning — the loop
1. **Observe:** exact symptom, exact time, exact error text/codes. "Outlook
   crashes" is not an observation; "Outlook 1000, module ntdll,
   `0xC0000374`, daily ~09:05" is.
2. **Correlate:** what else happened at those times (events, changes, logons,
   updates)?
3. **Hypothesize:** name a mechanism that would produce *all* the evidence.
4. **Test:** prefer tests that discriminate between hypotheses (disable the
   suspect add-in on one machine) over tests that merely might help (reboot).
5. **Conclude and document:** record cause, evidence, and fix — the writeup is
   what turns an incident into fleet knowledge.

## Impact
Teams that skip step 1 chase ghosts; teams that skip step 5 solve the same
problem quarterly.

## Related Entries
- V1.C1.E002 — layered model · V1.C1.E004 — first-response collection

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C1.E002
title: "Symptom vs. Cause: The Layered Diagnostic Model"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
 
status: draft
---

## Overview
Windows failures surface at a different layer than they originate. The
encyclopedia's recurring pattern — NTFS 55 caused by a dying disk, app crashes
caused by an injected DLL, lockouts caused by a phone — generalizes into a
model: locate the *symptom's* layer, then walk down until the evidence stops.

## Meaning — the stack for triage
| Layer | Symptom vocabulary | Ground truth sources |
|---|---|---|
| Application | Crashes 1000/1026, hangs 1002 | App logs, WER, dumps |
| Runtime/frameworks | CLR/VC++ codes, loader errors | 1026, Fusion, loader codes `0xC0000135/142` |
| OS services & subsystems | SCM 70xx, COM/RPC errors | System log, service-specific channels |
| Kernel & drivers | Bugchecks, 129 resets, PnP 219 | Minidumps, System log, LiveKernelEvents |
| Hardware & firmware | WHEA, disk 7/11, thermal 109 | WHEA records, SMART, vendor logs |
| Environment | Time skew, DNS/DC reachability, policy | Netlogon/GP/Time channels, dsregcmd |

Rule of walking down: a layer is only "cleared" when its ground-truth source
is clean — not when it merely looks plausible. Rule of stopping: the root layer
is the deepest one with *positive* evidence; don't blame hardware without a
hardware-layer fact.

## Related Entries
- V2.C4 intro — the storage chain as a worked example

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C1.E003
title: "Reproducibility, Baselines, and Change Tracking"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
 
status: draft
---

## Overview
Three questions shrink any investigation: Can we make it happen on demand?
What did "healthy" look like? What changed? Windows keeps enough state to
answer the last two even when nobody prepared.

## Diagnostic Procedure
1. **Reproducibility:** classify the failure — deterministic (same trigger →
   same failure), periodic (clock/time-driven: look at scheduled tasks,
   maintenance windows, GP refresh ~90 min, daily 03:00-ish maintenance), or
   sporadic (environment/load-driven). The class dictates strategy:
   deterministic → trace it live (ProcMon/WPR); periodic → find the timer;
   sporadic → arm persistent capture (LocalDumps, extended logs) and wait.
2. **Baseline from the machine itself:** Reliability Monitor
   (`perfmon /rel`) charts weeks of crashes/updates; the System log's
   6005/6013 rhythm shows uptime habits; `WinSAT`-era and
   Diagnostics-Performance boot events show what boot *used* to cost.
3. **Change inventory — the honest list:**
```powershell
# Updates
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10
# Recent software (registry uninstall keys, both bitness)
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
                 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' |
  Where-Object InstallDate | Sort-Object InstallDate -Descending |
  Select-Object DisplayName, DisplayVersion, InstallDate -First 15
# New services & drivers
Get-WinEvent -FilterHashtable @{LogName='System'; Id=7045} -MaxEvents 10 | Select-Object TimeCreated, Message
```
4. Correlate first-failure time against the change list before forming any
   hypothesis — "what changed" resolves a plurality of enterprise incidents
   by itself.

## Related Entries
- V1.C3.E002 — Reliability Monitor · V2.C3.E7045 — new services

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C1.E004
title: "First-Response Data Collection (What to Grab Before Rebooting)"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
 
status: draft
---

## Overview
The reboot that "fixes" the machine also destroys the crime scene: process
state, hang conditions, volatile counters, unsaved queues. A first-response
kit — collected in minutes, before remediation — preserves what an
investigation later needs. This is precisely the philosophy behind
purpose-built collector tooling: gather everything defensible, log every
collection failure explicitly, package it.

## Diagnostic Procedure
Volatile first (lost at reboot), persistent second:
1. **If something is hung right now:** dump it before touching it (Task
   Manager → Create dump file, or `procdump -ma <pid>`).
2. Volatile snapshot:
```powershell
$out = 'C:\Diag\firstresponse'; New-Item $out -ItemType Directory -Force | Out-Null
Get-Process | Sort-Object WS -Descending | Select-Object -First 40 Name, Id, WS, CPU, StartTime |
  Export-Csv "$out\processes.csv" -NoTypeInformation
Get-Service | Export-Csv "$out\services.csv" -NoTypeInformation
Get-NetTCPConnection -State Established | Export-Csv "$out\tcp.csv" -NoTypeInformation
tasklist /svc > "$out\tasklist-svc.txt"
```
3. Persistent evidence:
```powershell
'System','Application','Security','Microsoft-Windows-WindowsUpdateClient/Operational' |
  ForEach-Object { wevtutil epl $_ ("$out\" + ($_ -replace '[\\/]','-') + '.evtx') }
Copy-Item C:\Windows\Logs\CBS\CBS.log $out -ErrorAction SilentlyContinue
Copy-Item C:\Windows\Minidump\* $out -ErrorAction SilentlyContinue
Copy-Item 'C:\ProgramData\Microsoft\Windows\WER\ReportQueue' "$out\WER" -Recurse -ErrorAction SilentlyContinue
```
4. Context notes file: symptom, time, user, what was tried. Then — and only
   then — remediate.
5. Fleet form: automate this kit; ensure failed collections are *reported*
   (access denied, policy-blocked WER, missing channels) rather than silently
   skipped, so absence of data is itself data.

## Impact
Ten minutes of collection converts "it happened again and we still don't know
why" into a solvable case file.

## Related Entries
- V1.C3.E009 — building your own collector · V3.C1.E004 — WER locations

## References & Attribution
- original synthesis — License: n/a
