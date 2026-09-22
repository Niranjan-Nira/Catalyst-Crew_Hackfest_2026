# Volume I · Chapter 3 — The Diagnostic Toolbox

The tools referenced throughout the encyclopedia, each with its niche, its
sharpest use, and its trap. Rule of selection: pick the tool whose *native
question* matches yours — "what happened" (logs), "what is happening" (live
monitors), "why is it slow" (tracing), "what is this process doing"
(Sysinternals).

---
entry_id: V1.C3.E001
title: "Event Viewer (eventvwr) Deep Dive"
category: tool
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The GUI over everything Volume II documents. Its underused features: **Custom
Views** (persistent cross-log filters — build one for Level 1–2 across
System+Application as a daily driver), **Filter → XML tab** (hand-edit for
field-level filters the basic tab can't express, then reuse in
`Get-WinEvent -FilterXml`), **attach task to event** (fire a script on a
specific ID), and opening saved `.evtx` from other machines (expect missing
descriptions when the source machine's manifests aren't present — the data is
intact; see V2.C1.E005).

## Meaning — traps
- Filtering the GUI on huge Security logs is slow; server-side XPath via
  PowerShell scales better (V2.C1.E006).
- "Administrative Events" custom view mixes benign chronic errors into every
  look — build scoped views instead.

## Related Entries
- V2.C1.E005 / V2.C1.E006

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C3.E002
title: "Reliability Monitor (perfmon /rel)"
category: tool
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The most underrated triage tool in Windows: a day-by-day timeline of
application failures, Windows failures, warnings, and *informational changes*
(updates, installs) on one chart — the "what changed vs. when it broke"
question answered visually in ten seconds. Data comes from the RAC task
aggregating WER and event data; programmatic access via
`Win32_ReliabilityRecords` (V3.C3.E001) feeds the same picture into fleet
tooling.

## Diagnostic Procedure
1. `perfmon /rel` — read the failure clusters against the install markers.
2. Fleet form:
```powershell
Get-CimInstance Win32_ReliabilityRecords |
  Select-Object -First 20 TimeGenerated, SourceName, EventIdentifier, ProductName
```

## Related Entries
- V1.C1.E003 — baselines · V3.C3.E001

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C3.E003
title: "Performance Monitor and Data Collector Sets"
category: tool
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
PerfMon answers *quantified* questions — is the disk saturated, is memory
leaking, which process owns the IOPS — via counters; **Data Collector Sets**
record them unattended for intermittent problems. The high-yield counter
shortlist: `\LogicalDisk(*)\Avg. Disk sec/Read|Write` (latency — the disk
truth, >25 ms sustained is trouble), `\Memory\Available MBytes` +
`Pool Nonpaged Bytes` (leak hunting), `\Processor(_Total)\% Processor Time`
with `\System\Processor Queue Length`, `\Process(*)\Handle Count` trending
(handle leaks).

## Diagnostic Procedure
1. Disposable 24-hour collector:
```cmd
logman create counter DiagPerf -c "\LogicalDisk(*)\Avg. Disk sec/Read" "\LogicalDisk(*)\Avg. Disk sec/Write" "\Memory\Available MBytes" "\Process(*)\Handle Count" -si 00:00:15 -o C:\Diag\perf
logman start DiagPerf
:: later
logman stop DiagPerf
```
2. Open the `.blg` in PerfMon; scale, and read trends not instants.

## Related Entries
- V9.* — performance volume (queued)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C3.E004
title: "Resource Monitor and Task Manager Internals"
category: tool
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Task Manager for the 10-second look (add columns: Command line, Elevated,
Platform); Resource Monitor (`resmon`) for the 2-minute look — its unique
powers: **Disk tab** shows per-file I/O live (who is hammering the disk and on
*which file*), **CPU tab → Analyze Wait Chain** resolves "this process is hung
on that process," **Associated Handles** search finds which process holds a
locked file, **Network tab** maps connections to processes without a packet
capture.

## Meaning — traps
- Task Manager's "Disk %" is a heuristic; latency counters (E003) are the
  truth for storage health.
- Suspended UWP processes look alarming and are normal.

## Related Entries
- V2.C7.E1002 — wait-chain use for hangs

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C3.E005
title: "Sysinternals Suite (ProcMon, ProcExp, Autoruns, PsTools)"
category: tool
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The essential four. **Process Monitor**: every file/registry/process operation
with stack traces — the tool for "what is this app actually touching";
filter discipline is the skill (start with Process Name + Result ≠ SUCCESS;
`ACCESS DENIED` and `NAME NOT FOUND` on plausible paths solve most app-config
mysteries). **Process Explorer**: live process internals — DLLs and handles
(find who loaded the suspect DLL from a 1000 event; find who holds the file),
verify signatures, per-thread stacks. **Autoruns**: every autostart, shell
extension, and add-in — the injection-bisect tool for V2.C7 crash/hang
hunting (hide Microsoft entries, disable suspects, retest). **PsTools**:
`psexec` for SYSTEM-context reproduction, `pslist/pskill` remotely.

## Meaning — traps
- ProcMon captures everything; without filters the signal drowns — and
  boot-logging fills disks if forgotten.
- Kill Process trees from ProcExp on service hosts can destabilize a session
  host — dump first, kill second.
- Run tools from a Microsoft-downloaded copy; some environments flag renamed
  or repacked Sysinternals binaries.

## Related Entries
- V2.C7.E1000/E1002 — where these tools get used

## References & Attribution
- original synthesis — License: n/a (tools by Microsoft Sysinternals — referenced)

---
entry_id: V1.C3.E006
title: "Windows Performance Recorder/Analyzer (WPR/WPA) and ETW"
category: tool
severity_for_triage: informational
applies_to: ["Windows 8+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
ETW is the kernel-grade tracing fabric under the event log, WPR is its
recorder (built-in: `wpr.exe`, GUI or command line, profile-based —
CPU, disk, boot, etc.), WPA the analyzer. This is the escalation tier for
"why is it slow" questions the counters can't answer: slow boot/logon
decomposition, CPU sampling with stacks, wait analysis, disk I/O attribution.

## Diagnostic Procedure
1. General slowness capture (keep it short — traces are large):
```cmd
wpr -start GeneralProfile -start DiskIO -start FileIO
:: reproduce the slowness (60–120 s)
wpr -stop C:\Diag\slow.etl
```
2. Boot/logon issues: use the boot scenario (`wpr -boot` semantics or the
   xbootmgr legacy from the ADK) and analyze the phases in WPA.
3. In WPA, load symbols and start from the graphs matching the complaint
   (CPU Usage (Sampled) for compute; Disk Usage for I/O; the Regions of
   Interest for boot phases).

## Meaning — traps
ETL analysis has a learning curve; capture with the right profile beats
capturing everything — and for boot problems remember the free tier first:
Diagnostics-Performance events 100–110 already name slow-boot offenders
without any trace.

## Related Entries
- V2.C12.E005 — boot degradation events

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C3.E007
title: "DISM, SFC, and Component Store Repair"
category: tool
severity_for_triage: informational
applies_to: ["Windows 8+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The system-file integrity pair, in the correct order: **DISM
/Cleanup-Image** repairs the component store (the source of truth), **SFC
/scannow** repairs live system files *from* that store. Running SFC against a
corrupt store "finds errors it cannot fix" forever. Full workflow, sources for
offline machines, and the escalation ladder: V4.C2.E003. SFC's detail log is
inside `CBS.log` (lines tagged `[SR]`):
```powershell
Select-String -Path C:\Windows\Logs\CBS\CBS.log -Pattern '\[SR\]' | Select-Object -Last 40
```

## Related Entries
- V4.C2.E003 — the full repair workflow

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C3.E008
title: "msinfo32, dxdiag, and Hardware Inventory Tools"
category: tool
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
**msinfo32**: the one-stop system summary — BIOS/firmware version and mode,
Secure Boot state, memory, and crucially *Resources → Conflicts* and
*Software Environment → Windows Error Reporting* views; exports whole-machine
state (`msinfo32 /nfo C:\Diag\sys.nfo`) for tickets. **dxdiag**: display/audio
stack versions and the WHQL story for GPU triage (`dxdiag /t C:\Diag\dx.txt`).
PowerShell equivalents for fleet collection:
```powershell
Get-CimInstance Win32_ComputerSystem, Win32_BIOS, Win32_BaseBoard |
  Format-List *
Get-CimInstance Win32_PnPEntity | Where-Object ConfigManagerErrorCode -ne 0 |
  Select-Object Name, DeviceID, ConfigManagerErrorCode   # devices in error state
```
ConfigManagerErrorCode is the numeric form of Device Manager's yellow-bang
codes (10 = cannot start, 28 = no driver, 43 = device reported failure, 45 =
not present).

Honest limits worth documenting in any inventory tool: consumer-grade
sensors (CPU temperature, fan RPM, PSU rail voltages) are not reliably
exposed through standard Windows APIs on most enterprise hardware — vendor
WMI namespaces or agents are required, and their absence should be recorded
as "unavailable," not zero.

## Related Entries
- V1.C1.E004 — first-response kit · V2.C12.E007 — Kernel-PnP events

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C3.E009
title: "Building Your Own Collector: PowerShell Diagnostic Automation"
category: procedure
severity_for_triage: informational
applies_to: ["Windows 10/11 fleets"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Every mature IT shop eventually builds a collector: one command that gathers
the first-response kit (V1.C1.E004), inventory, logs, and health signals into
a package a human or pipeline can analyze. Design principles that separate
good collectors from script piles:

1. **PowerShell-native, no dependencies** — must run on any enterprise laptop
   as-shipped; no Python, no modules from the gallery.
2. **Modular** — one script per concern (events, storage, network, WER,
   inventory), orchestrated; failures isolated per module.
3. **Explicit failure visibility** — every collection that fails writes *why*
   (access denied, policy-blocked, feature absent) into a status log; silent
   skips are how collectors lie.
4. **Phase separation** — static point-in-time snapshots vs. time-window live
   monitoring (background jobs sampling counters/events concurrently) vs.
   packaging; don't serialize a 30-minute monitor behind static collection.
5. **Honest hardware claims** — document which metrics standard APIs cannot
   provide (temperatures, fan RPM, mains voltage) rather than emitting
   plausible zeros.
6. **Deterministic output layout** + a manifest (what ran, versions, hashes,
   duration, failures) so downstream tooling can trust the package.
7. **Encoding hygiene** — scripts saved UTF-8/ASCII-safe; smart-quote
   corruption from rich-text editors is a classic self-inflicted syntax
   failure; keep sources in a real editor/repo.

## Diagnostic Procedure — skeleton
```powershell
$run = Join-Path 'C:\Diag' (Get-Date -Format 'yyyyMMdd-HHmmss')
$status = New-Object System.Collections.Generic.List[object]
foreach ($mod in Get-ChildItem "$PSScriptRoot\modules\*.ps1") {
  try   { & $mod.FullName -OutputRoot $run
          $status.Add(@{Module=$mod.Name; Result='OK'}) }
  catch { $status.Add(@{Module=$mod.Name; Result='FAIL'; Error=$_.Exception.Message}) }
}
$status | ConvertTo-Json | Set-Content "$run\status.json"
Compress-Archive -Path $run -DestinationPath "$run.zip"
```

## Related Entries
- V7.C2.* — automation patterns (jobs vs runspaces, packaging) (queued)

## References & Attribution
- original synthesis — License: n/a
