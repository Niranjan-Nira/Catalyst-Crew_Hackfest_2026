# Volume III · Chapter 1 — Windows Error Reporting: Architecture and Report Anatomy

---
entry_id: V3.C1.E001
title: "The WER Pipeline: From Fault to Report to Microsoft"
category: concept
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Windows Error Reporting is the OS-wide crash/hang/failure telemetry pipeline.
When a process faults, `WerFault.exe` is invoked in the failing process's
context, snapshots the failure (parameters, optionally a dump), writes a local
report, and — policy permitting — uploads a signature to Microsoft, which may
respond with a known-solution link. Even fully offline, the *local* reports are
a rich forensic archive.

## Historical / Technical Context
WER replaced XP-era "Dr. Watson." Vista integrated it into the kernel's
unhandled-exception path; Windows 7+ extended it to hangs (via the desktop
heartbeat), kernel LiveDumps, and non-crash "generic" reports that any app can
file via the WER API. Corporate deployments can redirect or disable uploads
while keeping local archiving.

## Meaning — the stages
1. **Fault** — unhandled exception, hang detection, or API-filed report.
2. **Signature** — event type + N parameters (see E005) computed to identify
   the failure class.
3. **Local store** — `Report.wer` (+ optional dumps/heaps) written to
   ReportArchive or ReportQueue (E004); Application-log event `1001` records
   the same signature.
4. **Upload/bucketing** — signature hashed into a Microsoft "bucket" (E003);
   response may request more data or return a solution.

## Related Entries
- V3.C1.E002 · V3.C1.E003 · V2.C7.E1001

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Windows Error Reporting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V3.C1.E002
title: "Report Anatomy: Report.wer Field-by-Field Reference"
category: wer
severity_for_triage: high
applies_to: ["Windows 7+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`Report.wer` is a UTF-16 key=value text file — openable in any editor — that
fully describes one failure instance. Reading it well means knowing which of
its ~40 lines carry the diagnosis. This is the reference.

## Message Text & Fields
**Identity block**
| Key | Meaning |
|---|---|
| `Version` / `EventType` | Report format version; failure class (`APPCRASH`, `AppHangB1`, `BEX64`, `CLR20r3`, `LiveKernelEvent`, …) — E005 decodes each |
| `EventTime` | FILETIME (100ns ticks since 1601 UTC) of the failure |
| `ReportType` | 1 crash, 2 hang, 3 generic, 4 kernel (values vary by version; treat as informational) |
| `Consent` | 1 = not sent, higher values = upload consent level |
| `ReportStatus` / `ReportIdentifier` | Upload state; GUID matching the report folder name |

**Signature block — the diagnosis for `APPCRASH`**
| Key | Meaning | How to use it |
|---|---|---|
| `Sig[0]` AppName / `Sig[1]` AppVersion / `Sig[2]` AppTimestamp | Faulting image identity (timestamp = PE link time, hex epoch) | Confirms exact binary build |
| `Sig[3]` ModuleName / `Sig[4]` ModuleVersion / `Sig[5]` ModuleTimestamp | Module where the exception surfaced | The module to suspect — but see caveat below |
| `Sig[6]` ExceptionCode | NTSTATUS of the exception | E006 decodes the codes |
| `Sig[7]` ExceptionOffset | RVA of the faulting instruction inside the module | With symbols, resolves to a function |

**Caveat (original synthesis):** the faulting *module* is where the exception
was raised, not necessarily where the bug lives — a corrupted heap set up by
module A frequently detonates inside `ntdll.dll` or `ucrtbase.dll`. Treat
`ntdll`/`kernelbase`/CRT as "crime scene," and hunt the perpetrator in the
loaded-module list and dump.

**Dynamic signature block**
| Key | Meaning |
|---|---|
| `DynamicSig[1]` | OS version string |
| `DynamicSig[2]` | Locale ID |
| `DynamicSig[22]/[23]` | Additional hang/crash sub-codes on newer builds |

**Context block**
| Key | Meaning |
|---|---|
| `UI[2]` | Full path of the faulting application |
| `LoadedModule[n]` | Every DLL loaded at failure time — scan for third-party injectors (shell extensions, AV hooks, overlays); an unexpected DLL here solves many "mystery crashes" |
| `AppPath` / `TargetAppId` / `TargetAppVer` | App identity for store/packaged apps |
| `OsInfo[n]` | Build, edition, update level lines |
| `File[0..]` | Attached artifacts (minidumps, heap dumps, triage files) and their disposition |

## Diagnostic Procedure
1. Locate reports (see E004), open `Report.wer`, read in this order:
   `EventType` → `Sig[6]` exception code → `Sig[3..5]` module → `Sig[7]` offset
   → scan `LoadedModule` list for foreign DLLs.
2. Convert `EventTime`:
```powershell
[DateTime]::FromFileTimeUtc(133497288000000000)
```
3. If a `.dmp` is attached (`File[0]`), continue in WinDbg (`V3.C2.E003`);
   the .wer alone classifies, the dump explains.

## Related Entries
- V3.C1.E005 — EventType decoder · V3.C1.E006 — exception codes

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — WER report contents — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — module-vs-culprit caveat, reading order — License: n/a

---
entry_id: V3.C1.E003
title: "Bucketing: How Microsoft Groups Crashes"
category: concept
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A **fault bucket** is the equivalence class Microsoft assigns to a failure
signature so that millions of identical crashes count as one issue. The bucket
ID appears in Application-log event `1001` ("Fault bucket <id>, type <n>") and
inside uploaded report responses.

## Meaning
- Same bucket across many machines ⇒ same underlying defect — powerful for
  fleet triage: group your 1001 events by bucket before investigating.
- "Type" values distinguish signature algorithms (crash vs. hang vs. generic).
- A response of "not available"/0 bucket means the report wasn't uploaded
  (consent/policy) — local signature grouping on `Sig[0..7]` achieves the same
  effect offline.

## Diagnostic Procedure
1. Fleet-style grouping from one machine's log:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Windows Error Reporting'; Id=1001} -MaxEvents 200 |
  Group-Object { ($_ .Message -split "`n")[0] } |
  Sort-Object Count -Descending | Select-Object Count, Name -First 15
```

## Related Entries
- V2.C7.E1001 — WER 1001 entry (queued)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — WER concepts — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V3.C1.E004
title: "Where Reports Live: ReportArchive, ReportQueue, and the Registry"
category: reference
severity_for_triage: informational
applies_to: ["Windows 7+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
WER stores reports per-scope: system context under ProgramData, user context
under each profile. Queue = pending upload (often with dumps still attached);
Archive = completed (dumps frequently pruned).

## Message Text & Fields
| Location | Contents |
|---|---|
| `C:\ProgramData\Microsoft\Windows\WER\ReportArchive` | Completed system-context reports |
| `C:\ProgramData\Microsoft\Windows\WER\ReportQueue` | Pending system-context reports (best dump-hunting ground) |
| `%LOCALAPPDATA%\Microsoft\Windows\WER\ReportArchive` / `ReportQueue` | Per-user equivalents |
| `HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting` | Machine policy: `Disabled`, `DontShowUI`, `LocalDumps`, consent |
| Folder naming | `<Type>_<AppId>_<hash>_<cab>_<GUID>` — Type prefix mirrors EventType |

## Diagnostic Procedure
1. Inventory recent reports newest-first:
```powershell
Get-ChildItem 'C:\ProgramData\Microsoft\Windows\WER\Report*' -Directory -Recurse |
  Sort-Object LastWriteTime -Descending |
  Select-Object LastWriteTime, Name -First 25
```
2. Note for enterprise collectors: Group Policy can disable WER or redirect
   dumps; a collector must detect and report "blocked by policy" rather than
   returning an empty result (registry `Disabled=1`, or corporate queue paths).

## Related Entries
- V3.C1.E007 — Controlling WER

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — WER settings — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V3.C1.E005
title: "Event Types: APPCRASH, AppHang, BEX, CLR20r3, LiveKernelEvent, and More"
category: reference
severity_for_triage: high
applies_to: ["Windows 7+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis (decoding widely documented type names)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`EventType` is the first triage fork in any WER report. Each type implies a
different signature layout and a different investigative path.

## Message Text & Fields
| EventType | Meaning | First move |
|---|---|---|
| `APPCRASH` | Native unhandled exception | Read `Sig[6]` code + module (E002/E006) |
| `AppHangB1` / `AppHangXProcB1` | UI thread stopped pumping messages (XProc = blocked on another process) | Hang dump + thread stacks; find the wait target |
| `BEX` / `BEX64` | Buffer-overrun/DEP class: exception subcode in `Sig[8]` (e.g., fail-fast `0xC0000409` with STATUS_STACK_BUFFER_OVERRUN semantics) | Treat as memory-safety failure; suspect corrupted stack/heap, security cookie trips, /GS or CFG violations |
| `CLR20r3` | Unhandled .NET exception (framework-era signature: app, assembly, method token) | Get the managed exception type from paired .NET Runtime `1026` event |
| `MoAppCrash` / `MoAppHang` | Packaged (Store/UWP) app crash/hang | Same as APPCRASH plus package identity |
| `LiveKernelEvent` (codes like `141`/`144`/`1a1`) | Kernel captured a live dump *without* bugchecking — GPU/USB/hardware timeouts dominate (`141` = graphics TDR family) | Analyze `C:\Windows\LiveKernelReports\*.dmp`; driver/firmware focus |
| `AppRadar` / `Generic` / component names | Non-crash reports filed via WER API (leaks, health telemetry) | Read report payload; usually informational |
| `PnPDriverImportError` / `PnPDeviceProblemCode` | Driver install/device problem reports | Pair with Kernel-PnP channel events |
| `WindowsUpdateFailure3` | Update failure report with error code in parameters | Jump to V4.C2.E002 error atlas |

## Related Entries
- V3.C1.E006 — exception codes · V3.C2.E005 — LiveKernelEvents

## References & Attribution
- original synthesis of publicly documented type semantics — License: n/a

---
entry_id: V3.C1.E006
title: "Exception Code Reference: 0xC0000005 and the Other Codes That Matter"
category: reference
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "Windows SDK (ntstatus.h) — referenced"
    license: "referenced, not reproduced"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`Sig[6]`/ExceptionCode is an NTSTATUS. A dozen codes cover the overwhelming
majority of real-world crashes; know these cold.

## Message Text & Fields
| Code | Name | What it means | Likely root cause |
|---|---|---|---|
| `0xC0000005` | ACCESS_VIOLATION | Read/write of invalid memory | Null/dangling pointer, use-after-free, buffer overrun; occasionally genuinely bad RAM |
| `0xC0000409` | STACK_BUFFER_OVERRUN (fail-fast) | Security cookie/fail-fast triggered — the process *chose* to die | /GS violation, FastFail calls, CFG; memory-safety bug or deliberate abort |
| `0xC00000FD` | STACK_OVERFLOW | Thread stack exhausted | Runaway recursion; oversized stack allocations |
| `0xC0000374` | HEAP_CORRUPTION | Heap manager detected corrupted metadata | Overrun/double-free *earlier* than the crash point — enable PageHeap to catch the writer |
| `0xE0434352` | CLR exception ("`.CCR`") | Managed exception escaped to native | Read the real type from .NET Runtime `1026` |
| `0xE06D7363` | MSVC C++ exception ("`msc`") | Unhandled C++ `throw` | Application logic; vendor bug |
| `0xC0000135` / `0xC0000139` | DLL_NOT_FOUND / ENTRYPOINT_NOT_FOUND | Loader failed before main | Missing runtime (VC++ redist), wrong DLL version shadowing |
| `0xC0000142` | DLL_INIT_FAILED | A DllMain returned failure | Injected DLLs, desktop-heap exhaustion at logon storms |
| `0xC0000094` | INTEGER_DIVIDE_BY_ZERO | Arithmetic fault | Application logic on unexpected data |
| `0xC0000006` | IN_PAGE_ERROR | Paging in code/data failed | Failing disk, dying network share, corrupt executable — check disk events `7/51/153` |
| `0x80000003` | BREAKPOINT | int3 with no debugger | Assertion/fail paths in shipped code |
| `0xC0000008` | INVALID_HANDLE | Closed/foreign handle used | Handle bugs; sometimes handle-tracing needed |

**Heuristics (original synthesis):** `0xC0000374` and `0xC0000005`-inside-CRT
both mean "corruption happened earlier" — instrument with GFlags/PageHeap
rather than staring at the crash site. `0xC0000006` is the one code that
should send you to the *storage* logs first.

## Related Entries
- V3.C2.E003 — user-mode dump reading · V2.C4.E051 — disk paging errors

## References & Attribution
- Windows SDK ntstatus.h — code names referenced — not reproduced
- original synthesis — cause mapping and heuristics — License: n/a

---
entry_id: V3.C1.E007
title: "Controlling WER: Group Policy, Registry, LocalDumps, and Corporate Collection"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 7+ / Server 2008 R2+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Two control planes matter: policy (enable/disable/consent/redirect) and
**LocalDumps** — the switch that makes WER keep full user-mode dumps on disk
for any or specific executables. LocalDumps is the single most useful WER
setting for troubleshooting intermittent app crashes.

## Diagnostic Procedure
1. Check whether policy has WER disabled (a collector should surface this):
```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting' -ErrorAction SilentlyContinue |
  Select-Object Disabled, DontShowUI
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting' -ErrorAction SilentlyContinue
```
2. **[MODIFIES SYSTEM]** Enable full dumps for one problem application:
```powershell
$k = 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\MyApp.exe'
New-Item $k -Force | Out-Null
New-ItemProperty $k -Name DumpFolder -Value 'C:\Dumps' -PropertyType ExpandString -Force
New-ItemProperty $k -Name DumpType   -Value 2 -PropertyType DWord -Force   # 2 = full
New-ItemProperty $k -Name DumpCount  -Value 5 -PropertyType DWord -Force
```
   Reproduce the crash, collect `C:\Dumps\MyApp.exe.<pid>.dmp`, then remove the
   key. Note: LocalDumps fires only for WER-handled crashes (not for processes
   with their own crash handlers that swallow the exception).
3. Enterprise note: Group Policy under *Windows Error Reporting → Advanced*
   can redirect reports to a corporate queue and suppress Microsoft upload —
   the local anatomy in E002/E004 still applies.
4. Policy-blocked environments: when GPO disables dump collection, document
   the block explicitly in any diagnostic output instead of skipping silently.

## Related Entries
- V3.C1.E004 — report locations · V3.C2.E001 — dump types

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — collecting user-mode dumps / WER GP settings — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
