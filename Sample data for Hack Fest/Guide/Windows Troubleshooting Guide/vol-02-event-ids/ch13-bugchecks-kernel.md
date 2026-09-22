# Volume II · Chapter 13 — Bugchecks and the Kernel

A bugcheck (blue screen) is the kernel refusing to continue with corrupted or
contradictory state — a deliberate halt, not a crash in the user-mode sense.
Three records survive it: the BugCheck `1001` event, the dump file, and (for
hardware) WHEA records. This chapter reads the first and third; Volume III
Chapter 2 reads the dump.

---
entry_id: V2.C13.E001b
title: "BugCheck 1001: Reading the Stop Code Record"
category: event-id
event: { id: 1001, provider: "Microsoft-Windows-WER-SystemErrorReporting", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1001` (System log, source `BugCheck` / provider
WER-SystemErrorReporting) — "The computer has rebooted from a bugcheck. The
bugcheck was: 0x000000d1 (0x…, 0x…, 0x…, 0x…). A dump was saved in: …" — is
written at the boot after a blue screen. It carries the stop code, the four
parameters, and the dump path. Do not confuse it with Application-log 1001
(WER) — same ID, different provider/channel (V2.C1.E001's lesson in action).

## Message Text & Fields
| Field | Meaning |
|---|---|
| Bugcheck code | The stop code — family table in E002 |
| Parameters 1–4 | Code-specific; their meaning is defined per stop code (e.g., for `0x50`: P1 = referenced address, P2 = access type) |
| Dump path | Usually `C:\Windows\MEMORY.DMP`; minidumps in `C:\Windows\Minidump` |
| Report Id | Links to the WER kernel report |

## Diagnostic Procedure
1. Bugcheck history with codes:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WER-SystemErrorReporting'; Id=1001} -MaxEvents 10 |
  Select-Object TimeCreated, Message | Format-List
```
2. Verify dumps exist and are being kept:
```powershell
Get-ChildItem C:\Windows\Minidump, C:\Windows\MEMORY.DMP -ErrorAction SilentlyContinue |
  Select-Object FullName, Length, LastWriteTime
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl' |
  Select-Object CrashDumpEnabled, MinidumpDir, AlwaysKeepMemoryDump
```
   (CrashDumpEnabled: 1 complete, 2 kernel, 3 small, 7 automatic. No dumps
   despite 1001s → page file too small/moved, disk space, or cleanup tools.)
3. Classify: same code repeatedly = one defect (driver/hardware pattern);
   varied codes = suspect memory/storage/overclock first (E002's rule).
4. Proceed to the dump (V3.C2.E004) — the 1001 event triages, the dump explains.

## Related Entries
- V2.C13.E002 — code families · V2.C2.E041 — the paired Kernel-Power record

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C13.E002
title: "The Stop Code Families"
category: reference
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "MicrosoftDocs — Windows driver documentation (bugcheck reference) — referenced"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A few families cover most real-world bugchecks. Two meta-rules before the
table: (1) **varied codes across crashes point below software** — RAM,
storage, power, overclocking — because random corruption picks random victims;
(2) a consistent single code with a consistent culprit module points at that
driver. The `!analyze -v` output (V3.C2) names a "Probably caused by" module —
treat it as a lead, not a verdict, especially when it names `ntoskrnl.exe`
(the victim of choice for memory corruption).

## Message Text & Fields — the families
| Code | Name | Mechanism | Dominant causes |
|---|---|---|---|
| `0x0A` | IRQL_NOT_LESS_OR_EQUAL | Kernel touched pageable memory at high IRQL | Drivers; occasionally RAM |
| `0x1E` | KMODE_EXCEPTION_NOT_HANDLED | Unhandled exception in kernel mode | Drivers; corrupted code (RAM/disk) |
| `0x3B` | SYSTEM_SERVICE_EXCEPTION | Exception in a system-call path | Drivers (GPU prominent), memory |
| `0x50` | PAGE_FAULT_IN_NONPAGED_AREA | Reference to invalid system memory | Bad RAM, driver bugs, corrupt NTFS/AV filters |
| `0x7E` | SYSTEM_THREAD_EXCEPTION_NOT_HANDLED | Thread exception in a driver | The named driver in P-data |
| `0x9F` | DRIVER_POWER_STATE_FAILURE | Driver blocked a power transition | Storage/network/GPU drivers during sleep/resume — pairs with Modern Standby issues (V2.C2.E142) |
| `0xD1` | DRIVER_IRQL_NOT_LESS_OR_EQUAL | 0x0A, specifically by a driver | Network and storage drivers lead |
| `0x116/0x117` (+ LiveKernelEvent 141) | VIDEO_TDR family | GPU stopped responding; TDR recovery failed (116) or succeeded (LKE 141) | GPU driver/hardware/thermal |
| `0x124` | WHEA_UNCORRECTABLE_ERROR | CPU/machine-check reported fatal hardware error | Hardware: CPU/cache, VRM/power, thermal, firmware — read the WHEA record (E003) |
| `0x133` | DPC_WATCHDOG_VIOLATION | DPC/dispatch level ran too long | Storage drivers (classically NVMe/AHCI), network drivers |
| `0x139` | KERNEL_SECURITY_CHECK_FAILURE | Kernel fail-fast: corruption detected (list entry, stack cookie) | Drivers corrupting structures; RAM |
| `0xEF` | CRITICAL_PROCESS_DIED | A protected process (csrss, wininit, services) exited | Disk/file corruption of system binaries, AV/EDR interference, failing storage |
| `0x7B` | INACCESSIBLE_BOOT_DEVICE | Boot volume unreachable at kernel init | Storage driver/mode change (AHCI↔RAID), missing driver after image move |
| `0x7A`/`0x77` | KERNEL_DATA/STACK_INPAGE_ERROR | Paging in kernel data failed | Failing disk under pagefile — pairs with disk 51 (V2.C4.E051) |

## Meaning — routing rules (original synthesis)
- `0x124` → hardware path immediately: WHEA record, firmware/microcode,
  thermals, PSU; driver hunting wastes time here.
- `0x133`/`0xD1` with storage parameters → storage driver/firmware before
  anything else (correlate with 129 resets, V2.C4.E129).
- `0x9F` → `!analyze` names the blocked IRP's driver; sleep-path testing.
- `0xEF` → check disk health and recent servicing first; a dying disk
  corrupting system binaries is the classic story.
- Anything + memory-corruption signature (`0x139`, varied codes) → memtest
  before deep dump analysis; verify with Driver Verifier only after RAM is
  cleared (Verifier itself induces bugchecks by design — controlled use only).

## Related Entries
- V3.C2.E004 — reading the kernel dump · V2.C13.E003 — WHEA

## References & Attribution
- Microsoft bugcheck code reference (driver docs) — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — routing rules — License: n/a

---
entry_id: V2.C13.E003
title: "WHEA-Logger 17/18/19/47: Hardware Error Records"
category: event-id
event: { id: 18, provider: "Microsoft-Windows-WHEA-Logger", channel: System, level: Error }
severity_for_triage: high
applies_to: ["Windows Vista+ on WHEA-capable hardware"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Windows Hardware Error Architecture records what the *hardware itself*
reported: `17` corrected machine check (recovered — no crash), `18` fatal
machine check (usually alongside a 0x124), `19` corrected PCI Express error,
`47` corrected memory error (ECC systems), `1` generic record. WHEA events are
the rare log entries that genuinely mean "hardware," and the corrected ones
(17/19/47) are the early-warning tier — errors the machine survived.

## Meaning
The record's fields name the reporting component: Error Source (Machine Check
Exception, Corrected Machine Check, PCIe), Processor APIC ID (which core), and
for PCIe the Bus:Device:Function (map to the exact device). Interpretation:
occasional corrected errors on a years-old box = aging but functioning;
*trending* corrected errors = schedule replacement; any 18/0x124 = treat as
hardware incident (thermals, power delivery, firmware/microcode, then CPU/board
RMA path). On overclocked/XMP systems, first step is always stock settings.

## Diagnostic Procedure
1. WHEA history with trend:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'} -MaxEvents 50 |
  Group-Object Id | Select-Object Name, Count
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'} -MaxEvents 20 |
  Select-Object TimeCreated, Id, Message | Format-List
```
2. For PCIe (19): decode Bus:Device:Function against `Get-PnpDevice`
   locations to name the card/slot.
3. Corrected-memory trend (47) on ECC hardware: vendor DIMM diagnostics; the
   event usually identifies the memory controller/channel.
4. Firmware/microcode currency check — many 0x124/WHEA storms on given CPU
   generations are fixed by BIOS updates carrying microcode.

## Impact
WHEA is the difference between "random bluescreens" and a documented hardware
failure narrative — collect it in every diagnostic package.

## Related Entries
- V2.C13.E002 — 0x124 routing · V2.C2.E109 — thermal shutdowns

## References & Attribution
- original synthesis — License: n/a
