# Volume III · Chapter 2 — Crash Dump Analysis

The dump is where classification ends and explanation begins. This chapter is
deliberately practical: enough WinDbg to extract verdicts from the two dump
situations that dominate real work — a user-mode application crash and a
kernel bugcheck — plus the LiveKernelEvent middle ground.

---
entry_id: V3.C2.E001
title: "Dump Types: Minidump, Kernel, Complete, Active, Triage"
category: reference
severity_for_triage: informational
applies_to: ["all supported versions"]
sources:
  - repo: "MicrosoftDocs — debugger documentation — referenced"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
"A dump" is several different artifacts; knowing which you have (or should
configure) decides what questions it can answer.

## Meaning
**Kernel-side (CrashControl settings, written at bugcheck):**
| Type | Contents | Answers |
|---|---|---|
| Small memory dump (minidump, 256KB–~1MB) | Stop code, params, basic stacks, loaded module list | Which driver, basic verdict — enough for `!analyze` triage |
| Kernel memory dump | All kernel-mode memory | Full kernel analysis: IRPs, pools, driver state — the sweet spot |
| Automatic memory dump (default) | Kernel dump with smart pagefile sizing | Same as kernel |
| Complete memory dump | All RAM incl. user mode | Everything — huge; needed only when user-mode state matters to a kernel question |
| Active memory dump | Complete minus irrelevant pages (VM-friendly) | Near-complete at lower size |

**User-mode:**
| Type | Source | Answers |
|---|---|---|
| Full user dump (`DumpType=2` LocalDumps, ProcDump `-ma`) | Entire process space | Everything about the process — always prefer for crash analysis |
| Minidump (`-mm`) | Stacks + basics | Quick verdicts; often too little for heap questions |
| Hang dump (procdump `-h`, Task Manager on a live process) | Snapshot of a *running* process | Wait chains, deadlocks (V2.C7.E1002 workflow) |

**Triage dumps:** Windows also self-collects compact kernel "LiveDumps" into
`C:\Windows\LiveKernelReports` without crashing (E005).

Configuration reminder: kernel dumps require a page file on the system drive
large enough for kernel memory; "no dump appeared" usually means page-file
policy, disk space, or a cleanup tool (V2.C13.E001b step 2).

## Related Entries
- V3.C1.E007 — LocalDumps setup · V3.C2.E005 — LiveKernelEvents

## References & Attribution
- Microsoft debugger docs — dump types — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — selection guidance — License: n/a

---
entry_id: V3.C2.E002
title: "WinDbg Setup, Symbols, and !analyze -v"
category: procedure
severity_for_triage: high
applies_to: ["analysis workstation — any supported Windows"]
sources:
  - repo: "MicrosoftDocs — debugger documentation — referenced"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Analysis happens on *your* workstation, not the patient: copy dumps off,
open them in WinDbg (the Store/winget `WinDbg` app, or the ADK's classic
windbg.exe). Symbols are non-negotiable — without Microsoft's symbol server,
stacks are meaningless addresses.

## Diagnostic Procedure
1. Install:
```cmd
winget install Microsoft.WinDbg
```
2. Symbol path — set once (environment variable applies to all debuggers):
```cmd
setx _NT_SYMBOL_PATH "srv*C:\Symbols*https://msdl.microsoft.com/download/symbols"
```
   Air-gapped analysis: pre-populate `C:\Symbols` on a connected machine with
   the same OS build's symbols, or accept module-level-only verdicts.
3. Open the dump (File → Open dump, or `windbg -z C:\Diag\MEMORY.DMP`) and run
   the universal first command:
```text
!analyze -v
```
   Read in this order: **stop/exception code** and parameters → **FAULTING
   SOURCE/PROCESS** → the **STACK_TEXT** (bottom = how it got there, top =
   where it died) → **MODULE/Probably caused by** (a lead, not a verdict —
   `ntoskrnl`/`memory_corruption` verdicts mean "look elsewhere," usually RAM
   or another driver's damage).
4. Universal orientation commands regardless of dump kind:
```text
lm            ; loaded modules with versions/timestamps
!sysinfo machineid   ; hardware identity (kernel dumps)
.time         ; crash time and uptime
```
5. Verify suspect-module identity before blaming: `lmvm <module>` shows path,
   version, and link date — the "old driver from 2019 in a 2026 system" read.

## Related Entries
- V3.C2.E003 / V3.C2.E004 — the two workflows this feeds

## References & Attribution
- Microsoft debugger docs — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — reading order — License: n/a

---
entry_id: V3.C2.E003
title: "Reading a User-Mode Crash: Stack, Modules, Exception Context"
category: procedure
severity_for_triage: high
applies_to: ["analysis workstation"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Input: a `.dmp` from LocalDumps/WER/ProcDump for a crash you triaged via
event 1000 (module + exception code already known). Goal: the faulting call
path and the responsible component.

## Diagnostic Procedure
1. `!analyze -v` first — for user dumps it prints the exception record,
   faulting stack, and a bucket-style verdict.
2. Orient manually when needed:
```text
.ecxr          ; switch to the exception context (the crash moment)
kb             ; stack with parameters at that context
~*k            ; stacks of ALL threads (essential for hangs/deadlocks)
lm             ; module list — hunt third-party DLLs in-process
!heap -s       ; heap summary (corruption cases)
```
3. Read the stack for the *transition*: frames usually run
   app code → third-party DLL → Windows DLLs. The interesting frame is the
   last non-Microsoft one before the fault — that component owned the
   operation. (The E002 caveat: with `0xC0000374` heap verdicts, the
   corruptor already left; instrument with PageHeap and catch the next one:
   `gflags /p /enable App.exe /full`.)
4. Hang dumps: skip `.ecxr` (no exception); go straight to `~*k` and find the
   UI thread (thread 0 usually) — its top frames name the wait; cross-process
   waits show handle/ALPC frames whose owner you chase with the wait-chain
   view (V1.C3.E004).
5. Managed (.NET) dumps: load the SOS extension and use managed-stack
   commands:
```text
.loadby sos clr        ; .NET Framework   (coreclr for .NET 5+)
!clrstack
!pe                     ; the managed exception
```
6. Write the finding as: component + operation + evidence frames — that's
   what a vendor ticket needs.

## Related Entries
- V2.C7.E1000/E1002 — the events that led here · V3.C1.E006 — code meanings

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V3.C2.E004
title: "Reading a Kernel Bugcheck Dump"
category: procedure
severity_for_triage: high
applies_to: ["analysis workstation"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Input: MEMORY.DMP or a minidump plus the stop code from event 1001. Goal:
name the responsible driver or route to hardware.

## Diagnostic Procedure
1. `!analyze -v`, then interrogate its verdict with the E002 family
   knowledge: does the stack *show* the named module doing something wrong,
   or is it merely present?
2. Family-specific follow-ups:
```text
; 0x9F (power) — the analysis names a blocked IRP:
!irp <address>          ; who owns the stuck IRP → that driver
; 0x133 (DPC watchdog):
!dpcwatchdog            ; what was running long
; 0x124 (WHEA):
!errrec <address>       ; decode the hardware error record (P2 of the stop)
; suspected pool corruption:
!poolval / !verifier    ; if Driver Verifier was armed
```
3. The module hygiene pass — often the whole answer:
```text
lm t n                  ; all modules with timestamps
```
   Sort mentally by date: ancient third-party filter drivers (AV remnants,
   old vendor utilities, RGB/peripheral software) in a current OS are prime
   suspects; `lmvm <name>` for each candidate.
4. Recurring crashes without a clear culprit: arm **Driver Verifier** against
   third-party drivers only, reproduce, analyze the (now precise) verifier
   bugcheck — and know the exit: boot Safe Mode and `verifier /reset` if the
   machine crash-loops. **[MODIFIES SYSTEM]**
```cmd
verifier /standard /all   & REM prefer selecting only 3rd-party via GUI
```
5. Hardware routing: 0x124/WHEA content, multi-code randomness, or
   memory-corruption verdicts → memtest, stock clocks, firmware — before more
   dump time.

## Related Entries
- V2.C13.E002 — the routing rules this executes · V2.C13.E003 — WHEA records

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V3.C2.E005
title: "LiveKernelEvents: Diagnosing Hangs Without a Blue Screen"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 8+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
When a subsystem hangs but the kernel can recover — GPU TDR resets, USB
stalls, storage timeouts — Windows captures a **live kernel dump** instead of
crashing: WER logs a `LiveKernelEvent` (code `141` graphics, `144` USB, `1a1`
watchdog-class, etc.) and the dump lands in `C:\Windows\LiveKernelReports`
(subfolders per source: `WATCHDOG`, `USBHUB3`, etc.). Users report "screen
went black for two seconds" — this is where the evidence went.

## Diagnostic Procedure
1. Inventory:
```powershell
Get-ChildItem C:\Windows\LiveKernelReports -Recurse -Include *.dmp -ErrorAction SilentlyContinue |
  Select-Object FullName, Length, LastWriteTime
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Windows Error Reporting'; Id=1001} -MaxEvents 100 |
  Where-Object { $_.Message -match 'LiveKernelEvent' } | Select-Object TimeCreated, Message
```
2. Analyze like a kernel dump (`!analyze -v`): for code 141 the report names
   the display driver component that timed out (TDR); recurring 141 =
   GPU driver/thermal/hardware ladder — driver clean-install, thermal check,
   then hardware.
3. Correlate timestamps with user complaints and with System-log companions
   (Display driver `4101` "stopped responding and has recovered" for TDR).
4. Fleet note: LiveKernelReports is bounded in size and rotates; collect it
   in diagnostic packages before it self-prunes.

## Related Entries
- V3.C1.E005 — the LiveKernelEvent WER type · V2.C13.E002 — 0x116/0x117

## References & Attribution
- original synthesis — License: n/a
