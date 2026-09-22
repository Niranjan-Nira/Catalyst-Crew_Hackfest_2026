# Volume I · Chapter 2 — Windows Architecture for Troubleshooters

Just enough internals to make the event logs legible. Each entry ends with
"what breaks here" — the failure signatures that this piece of architecture
explains.

---
entry_id: V1.C2.E001
title: "Session 0, Sessions, and Window Stations"
category: concept
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---

## Overview
Since Vista, services live in **Session 0** and every interactive user gets
Session 1+. Services cannot show UI to users; a service that tries blocks
forever or fails silently. Each session has window stations/desktops with a
finite **desktop heap** — exhaustion produces bizarre "windows won't open" and
`0xC0000142` (DLL init failed) symptoms at logon storms on session hosts.

## Meaning — what breaks here
- Legacy services expecting UI → hangs, 7011 timeouts, invisible dialogs.
- Desktop-heap exhaustion (many services with interactive flags, RDS hosts) →
  sporadic process-start failures with `0xC0000142`.
- "Works when I run it manually, fails as a service" → session/profile/
  environment differences, not the binary.

## Related Entries
- V2.C3.E7011 · V3.C1.E006 (`0xC0000142`)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C2.E002
title: "The Service Control Manager (SCM)"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---

## Overview
`services.exe` owns the service database (registry under
`HKLM\SYSTEM\CurrentControlSet\Services`), launches services per start type
(boot/system/auto/delayed/demand), tracks their state machine
(START_PENDING → RUNNING → STOP_PENDING → STOPPED), enforces the 30-second
control window, and executes recovery actions on unexpected exits. The entire
7000-series of Volume II Chapter 3 is this component narrating its work.

## Meaning — what breaks here
- State-machine violations → 7009/7011 timeouts.
- Process death without SCM notification → 7031/7034.
- Registry `ImagePath`/account damage → 7000 with loader/logon errors.
- Shared-process (svchost) grouping: one bad service can take siblings down —
  since Windows 10 1703, services split into separate svchosts on machines
  with ≥3.5 GB RAM, reducing this class.

## Related Entries
- V2.C3.* — the SCM event chapter

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C2.E003
title: "The Boot Sequence: UEFI → Boot Manager → winload → Kernel → smss → Logon"
category: concept
severity_for_triage: informational
applies_to: ["Windows 10/11, UEFI systems"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---

## Overview
Boot failures are located by *how far* the machine got; each stage has a
distinct failure vocabulary.

## Meaning — stages and their failures
| Stage | Job | Failure vocabulary |
|---|---|---|
| UEFI firmware | POST, load `bootmgfw.efi` from the EFI System Partition | Firmware logo hang, "no bootable device" — firmware/ESP/disk level |
| Boot Manager (bootmgr) | Read BCD, pick OS entry | `0xC000000E/F` BCD errors, boot menu issues → `bcdedit`/`bootrec` territory |
| winload.efi | Load kernel, HAL, boot drivers; verify signatures | Driver-signature and missing-file errors naming the file |
| Kernel init | Start executive, boot/system drivers, mount system volume | Early bugchecks (`0x7B` INACCESSIBLE_BOOT_DEVICE = storage driver/mode change) |
| smss → csrss/wininit | Sessions, pagefile, registry ready | Session-manager errors, pagefile problems |
| Service start & logon (winlogon, LSA, SCM) | Auto services, credential UI | SCM 70xx storms, hangs at spinner — Diagnostics-Performance events 100–110 quantify |

WinRE (automatic after repeated failures) is the built-in triage environment:
Startup Repair logs to `C:\Windows\System32\LogFiles\Srt\SrtTrail.txt` — read
that file instead of re-guessing what it found.

## Related Entries
- V2.C13 — bugcheck families · V2.C12.E005 — boot-degradation events

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — boot process & WinRE — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — failure vocabulary mapping — License: n/a

---
entry_id: V1.C2.E004
title: "The Registry: Hives, Virtualization, and Transaction Logs"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---

## Overview
The registry is a set of hive files (`SYSTEM`, `SOFTWARE`, `SECURITY`, `SAM`,
`DEFAULT` under `C:\Windows\System32\config`; `NTUSER.DAT`/`UsrClass.dat` per
profile) with write-ahead `.LOG1/.LOG2` transaction logs that make hive
updates crash-consistent. `CurrentControlSet` is a symlink to `ControlSet00N`
chosen at boot; `LastKnownGood` semantics were retired in modern clients.

## Meaning — what breaks here
- Hive corruption (storage faults, torn writes) → boot failure or User Profile
  Service 1511/1533 for NTUSER hives; modern Windows auto-recovers hives from
  the transaction logs far more often than the XP-era folklore suggests.
- Profile hive locked/leaked handles → slow logoff, "registry remained in
  use" warnings (User Profile Service events 1530).
- Registry *virtualization* (legacy 32-bit apps writing HKLM redirected to
  per-user VirtualStore) → "settings changes don't apply for other users" —
  check `%LOCALAPPDATA%\VirtualStore` and the WOW6432Node split when values
  seem to vanish.

## Diagnostic Procedure
1. Hive health without third-party tools:
```cmd
reg query "HKLM\SYSTEM\Select" /v Current
```
2. For profile-hive issues, pair the User Profile Service 15xx events with
   handle hunting (Sysinternals `handle.exe -a ntuser.dat`).

## Related Entries
- V2.C8.E1530 — profile events (queued)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C2.E005
title: "NTFS, VSS, and the Storage Stack"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---

## Overview
An I/O travels: application → file system (NTFS + filter drivers) → volume/
partition managers → class driver (`disk.sys`) → port driver
(storahci/stornvme/vendor) → hardware. Each layer has its own events —
which is why Volume II Chapter 4 reads as a chain. **Filter drivers** (AV,
backup, dedup, EDR) stack *above* NTFS and are invisible suspects in file
weirdness; **VSS** snapshots power Previous Versions, backups, and System
Restore, and its writers are a frequent backup-failure culprit.

## Meaning — what breaks here
- Filter-driver conflicts → hangs on file ops, mysterious sharing violations
  (`fltmc filters` lists the stack and altitudes).
- VSS writer failures → backup errors citing writer names
  (`vssadmin list writers` shows state; unstable writers point at their
  owning service).
- Layer attribution: media errors (disk 7) vs. transport (11/129) vs.
  file-system verdicts (NTFS 55) vs. paging consequences (51) — the chain in
  V2.C4.

## Diagnostic Procedure
```cmd
fltmc filters
vssadmin list writers
vssadmin list shadows
```

## Related Entries
- V2.C4.* — the storage event chain

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C2.E006
title: "WMI/CIM Architecture and Repository Health"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---

## Overview
WMI (the Windows implementation of CIM) is management middleware: the
`Winmgmt` service hosts a repository (`C:\Windows\System32\wbem\Repository`)
of class definitions, and **providers** (in `wmiprvse.exe` hosts) answer
queries about hardware, OS, and applications. Monitoring agents, ConfigMgr
inventory, Group Policy filters, and half the diagnostic cmdlets in this
encyclopedia ride on it.

## Meaning — what breaks here
- Repository corruption → inventory/monitoring failures, `0x80041002/0x80041010`
  (class not found) errors, GP WMI filters silently failing.
- Provider misbehavior → `wmiprvse.exe` CPU/memory runaways (identify the
  hosted provider before blaming "WMI").
- Quota exhaustion on query-heavy servers.

Repair etiquette: `winmgmt /verifyrepository` first; `/salvagerepository`
next; full repository rebuild is the *last* resort — it forgets
non-recompiled third-party classes (agents must re-register).

## Diagnostic Procedure
```cmd
winmgmt /verifyrepository
```
```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption   # end-to-end smoke test
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-WMI-Activity/Operational'; Level=2} -MaxEvents 10
```

## Related Entries
- V7.C1.E002 — CIM cmdlet patterns

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V1.C2.E007
title: "COM, DCOM, and RPC Fundamentals"
category: concept
severity_for_triage: informational
applies_to: ["all versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---

## Overview
COM is Windows' in-process/out-of-process object plumbing (CLSIDs/AppIDs in
the registry, activation permissions per AppID); DCOM extends activation
across machines; RPC (with the endpoint mapper on 135/TCP plus dynamic ports)
is the transport under DCOM, WMI remoting, and much of Windows' own
inter-service chatter. "RPC server unavailable" (`0x800706BA`) is therefore a
*network/service reachability* symptom, not an RPC bug.

## Meaning — what breaks here
- DCOM 10016 (activation permission mismatches) — overwhelmingly benign OS
  self-noise; fix only when a real application activation fails with matching
  CLSID/AppID (full treatment: V2.C8.E10016).
- `0x800706BA` — target unreachable/firewalled/service down: test 135 + the
  dynamic range, confirm the serving process is alive.
- DCOM hardening (post-2021 authentication-level enforcement) — legacy
  clients failing against hardened servers with access-denied activations.

## Diagnostic Procedure
```powershell
Test-NetConnection <host> -Port 135
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-DistributedCOM'} -MaxEvents 10 |
  Select-Object TimeCreated, Id, Message
```

## Related Entries
- V2.C8.E10016 (queued) · V1.C2.E006 — WMI rides on this

## References & Attribution
- original synthesis — License: n/a
