# Volume II · Chapter 7 — Application Log: Crashes and Hangs

The crash quartet: `1000` (native crash) → `1001` (WER record for the same
failure) → dump on disk (Volume III). Hangs use `1002`; managed code adds
`.NET Runtime 1026/1023`. These events almost always arrive in pairs/triples
within seconds — read them as a set, keyed by process name, PID, and time.

---
entry_id: V2.C7.E1000
title: "Application Error 1000: The Application Crash"
category: event-id
event: { id: 1000, provider: "Application Error", channel: Application, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1000` — "Faulting application name: … Faulting module name: …
Exception code: …" — is the canonical crash record for native (and
native-surfaced) failures. It is the Application-log rendering of the same
signature that WER writes into `Report.wer` — everything in V3.C1.E002 about
interpreting module/code/offset applies verbatim here.

## Message Text & Fields
| Field | Meaning | Cross-reference |
|---|---|---|
| Faulting application name + version + time stamp | Crashing image identity (timestamp = PE link time) | `Sig[0..2]` |
| Faulting module name + version + time stamp | Module where the exception surfaced | `Sig[3..5]`; crime-scene caveat applies |
| Exception code | NTSTATUS | Decode via V3.C1.E006 |
| Fault offset | RVA inside the faulting module | Resolves to a function with symbols |
| Faulting process id / start time | Hex PID + FILETIME | Correlate with 7031/7034, 1001 |
| Faulting application path / module path | Full paths | Detects wrong-copy loads (two installs) |
| Report Id | GUID | Matches the WER report folder name (V3.C1.E004) |

## Meaning
1000 identifies the *what* (which binary, which exception, where). It cannot
identify the *why* by itself — that requires either pattern knowledge (module
and code combinations) or a dump. Fastest high-value read: exception code
first, then whether the faulting module is (a) the app itself, (b) a Microsoft
runtime/OS DLL, or (c) a third-party DLL you didn't expect in that process.

## Likely Root Causes
1. **Application defect** — faulting module is the app or its own libraries.
   *very common*
2. **Third-party injection** — shell extensions, AV/DLP hooks, overlays, input
   software appearing as the faulting module inside someone else's process.
   *very common on managed enterprise machines*
3. **Corrupted installation / mismatched DLL versions** — module path points
   somewhere unexpected; `0xC0000135/139/142` loader-class codes. *common*
4. **Heap corruption detonating in system DLLs** — `ntdll`/`ucrtbase` +
   `0xC0000374`/`0xC0000005`; real culprit earlier in time. *common*
5. **Hardware (RAM/storage)** — random modules, random codes, plus
   `0xC0000006` in-page errors. *uncommon*

## Diagnostic Procedure
1. Pull crashes for one application with parsed fields:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Error'; Id=1000} -MaxEvents 30 |
  Where-Object { $_.Message -like '*myapp.exe*' } |
  ForEach-Object {
    $d = ([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated; App=$d[0]; Module=$d[3]; Code=$d[6]; Offset=$d[7] }
  }
```
2. Group by Module+Code — one signature repeating is a single bug; scattered
   signatures point to injection or hardware.
3. Find the matching WER report via Report Id (V3.C1.E004) and check the
   `LoadedModule` list for foreign DLLs.
4. **[MODIFIES SYSTEM]** No dump attached? Enable LocalDumps for the exe
   (V3.C1.E007), reproduce, analyze (V3.C2.E003).

## Resolution
Keyed to causes: update/patch the app (1); isolate by removing/disabling the
injected component — clean-boot methodology or per-vendor exclusions (2);
repair-install, restore correct runtime redistributables (3); PageHeap/GFlags
to catch the corruptor, then fix or report it (4); memory and disk diagnostics
(5).

## Impact
User-facing data loss on crash; for services, pairs with SCM 7031/7034 into
availability incidents; fleet-wide new signatures after a change window are a
rollback trigger.

## Related Entries
- V2.C7.E1001 — the paired WER record
- V3.C1.E002 / V3.C1.E006 — signature and code decoding
- V2.C3.E7031 — service-crash pairing

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — application crash troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — triage grouping heuristics — License: n/a

---
entry_id: V2.C7.E1001
title: "Windows Error Reporting 1001: The WER Bucket Record"
category: event-id
event: { id: 1001, provider: "Windows Error Reporting", channel: Application, level: Information }
severity_for_triage: medium
applies_to: ["Windows Vista+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1001` — "Fault bucket <id>, type <n> / Event Name: <EventType> /
P1..P10: <signature parameters>…" — is WER's ledger entry: one per report,
whether crash, hang, kernel event, or update failure. Where 1000 exists only
for crashes, 1001 exists for *every* WER report type, which makes it the
single best event to mine for machine-health overviews.

## Message Text & Fields
| Field | Meaning |
|---|---|
| Fault bucket / type | Microsoft-side grouping id (V3.C1.E003); 0/absent if not uploaded |
| Event Name | The EventType — APPCRASH, AppHangB1, BEX64, CLR20r3, LiveKernelEvent, WindowsUpdateFailure3… (decoder: V3.C1.E005) |
| Response | Whether Microsoft returned a solution |
| Cab Id | Non-zero when additional data was uploaded |
| P1–P10 | Signature parameters — layout depends on Event Name (for APPCRASH: app, version, timestamp, module, version, timestamp, code, offset) |
| Attached files / storage path | Dump locations at report time — note that ReportQueue paths may be pruned later |

## Meaning
A P-signature is a machine-parsable fingerprint: identical P1–P8 across events
= the same defect. LiveKernelEvent 1001s reveal hardware/driver near-misses
that never bluescreened; WindowsUpdateFailure entries carry the update error
code without touching WU logs.

## Diagnostic Procedure
1. Health overview — count reports by Event Name over 30 days:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Windows Error Reporting'; Id=1001; StartTime=(Get-Date).AddDays(-30)} |
  ForEach-Object { ([xml]$_.ToXml()).Event.EventData.Data[2].'#text' } |
  Group-Object | Sort-Object Count -Descending
```
2. Extract full P-signatures for one Event Name and group for top offenders
   (index 2 = Event Name; indexes 5..14 = P1–P10 in the EventData array).

## Impact
For fleet analytics, 1001 is the cheapest crash-telemetry source that requires
no agent beyond event collection.

## Related Entries
- V3.C1.E003 — bucketing · V3.C1.E005 — EventType decoder
- V2.C7.E1000 — crash detail pairing

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — WER — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — mining patterns — License: n/a

---
entry_id: V2.C7.E1002
title: "Application Hang 1002"
category: event-id
event: { id: 1002, provider: "Application Hang", channel: Application, level: Error }
severity_for_triage: medium
applies_to: ["all supported versions"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1002` — "The program <exe> version <v> stopped interacting with Windows
and was closed…" — fires when a GUI process stops pumping its message queue
past the ghosting threshold (~5 s makes the window "Not Responding"; 1002 is
logged when the user or system then terminates it, or WER files an AppHang
report). It records that a hang *happened*; the paired `AppHangB1` WER report
(and a hang dump, if captured) says *where it was stuck*.

## Meaning
Hang ≠ crash: the process was alive but its UI thread was blocked — waiting on
I/O, a lock, a network call, or another process (`AppHangXProcB1` names the
cross-process case). Frequency and trigger context (file-open dialogs, network
drive access, printing) are the diagnostic gold.

## Likely Root Causes
1. **UI thread doing synchronous I/O to slow/unreachable targets** — network
   shares, dead printers, cloud drives. Classic: Explorer/Office hanging in
   the common file dialog because of a stale mapped drive or shell namespace
   extension. *very common*
2. **Shell extension / add-in deadlocks** (context-menu handlers, COM add-ins).
   *very common*
3. **Lock-order deadlocks inside the app or with injected hooks.** *common*
4. **GPU or print driver stalls surfacing as UI freezes.** *common*

## Diagnostic Procedure
1. Frequency and trigger inventory:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Hang'; Id=1002} -MaxEvents 30 |
  Select-Object TimeCreated, @{n='App';e={([xml]$_.ToXml()).Event.EventData.Data[0].'#text'}}
```
2. Capture the state *during* a hang — dump the process while it is stuck
   (Task Manager → right-click → Create dump file), then inspect the UI
   thread's stack (V3.C2.E003): the wait target is usually explicit
   (`NtWaitForSingleObject` under a named module tells the story).
3. For Explorer/Office: bisect shell extensions/add-ins (Autoruns' Explorer
   tab; Office safe mode `excel.exe /safe`).
4. Check reachability of every mapped drive and default printer — the two
   most-ignored hang sources on enterprise laptops.

## Resolution
Remove/repair the blocking extension or add-in; eliminate dead network
dependencies (unmap stale drives, fix DFS targets, remove offline default
printers); vendor fix for genuine app deadlocks — attach the hang dump to the
ticket.

## Impact
Hangs erode user trust faster than crashes ("the machine is slow") and are
underreported; recurring 1002s for Explorer degrade the entire desktop
session.

## Related Entries
- V3.C1.E005 — AppHangB1/XProcB1 semantics
- V2.C3.E7011 — the service-side analog

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C7.E1026
title: ".NET Runtime 1026: Unhandled Managed Exception"
category: event-id
event: { id: 1026, provider: ".NET Runtime", channel: Application, level: Error }
severity_for_triage: high
applies_to: [".NET Framework 4.x; .NET (Core) 5+ hosts"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1026` — "Application: <exe> / Framework Version: … / Description: The
process was terminated due to an unhandled exception. Exception Info:
<ExceptionType> at <Namespace.Class.Method>…" — is the CLR's own crash record,
and it is *better* than the paired 1000: it names the managed exception type
and often the failing method with a partial stack, no dump required.

## Meaning
Read 1026 **before** its paired 1000 for managed apps (the 1000 will just show
`0xE0434352` in some CLR/kernel module — nearly information-free). The
exception type does the triage:

| Exception type | Typical story |
|---|---|
| `System.NullReferenceException` | Plain application bug |
| `System.IO.*` / `UnauthorizedAccessException` | Environment: paths, permissions, redirected folders |
| `System.Configuration.ConfigurationErrorsException` | Malformed .config — frequently after manual edits |
| `System.IO.FileNotFoundException` (assembly load) | Missing dependency/runtime — check Fusion binding |
| `System.OutOfMemoryException` | Leak or genuinely huge workload; 32-bit process limits |
| `System.AccessViolationException` | Native interop corruption — treat as native crash |

## Diagnostic Procedure
1. Extract exception type + top frame per crash:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='.NET Runtime'; Id=1026} -MaxEvents 20 |
  Select-Object TimeCreated, @{n='Info';e={($_.Message -split "`n" | Select-String 'Exception Info|at ') -join ' | '}}
```
2. Pair with the 1000/1001 by time and PID for report/dump linkage.
3. For assembly-load failures, capture Fusion logs or use `dotnet --info` /
   runtime config review on .NET 5+.

## Related Entries
- V2.C7.E1000 · V3.C1.E005 (CLR20r3) · V3.C1.E006 (0xE0434352)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C7.E1023
title: ".NET Runtime 1023: Fatal Execution Engine Error"
category: event-id
event: { id: 1023, provider: ".NET Runtime", channel: Application, level: Error }
severity_for_triage: high
applies_to: [".NET Framework era primarily"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1023` — ".NET Runtime version <v> — Fatal Execution Engine Error
(<code>)…" — means the CLR *itself* failed: internal state corruption, not an
application exception. Rare, and its causes sit below the application:
corrupted framework installation, native interop trashing CLR structures,
profiler/instrumentation agents, or (historically) specific framework bugs
fixed in updates.

## Likely Root Causes
1. **Damaged .NET Framework installation** — repair via the .NET Repair Tool
   or OS servicing (`DISM /RestoreHealth` for in-box framework). *common*
2. **Native code (interop, injected profilers/APM agents) corrupting the
   runtime.** *common*
3. **Known framework defects — resolved by updating the framework/OS.** *common historically*
4. **Hardware memory errors.** *uncommon*

## Diagnostic Procedure
1. Inventory installed framework versions and patch level; update first.
2. Bisect instrumentation: remove APM/profiler agents (check
   `COR_ENABLE_PROFILING` in the process environment) and retest.
3. If persistent and machine-specific: RAM test; if app-specific across
   machines: capture a full dump for the vendor.

## Related Entries
- V2.C7.E1026 — ordinary managed crashes (contrast)

## References & Attribution
- original synthesis — License: n/a
