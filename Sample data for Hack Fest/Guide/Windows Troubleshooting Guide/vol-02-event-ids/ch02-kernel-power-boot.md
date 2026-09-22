# Volume II · Chapter 2 — System Log: Kernel, Power, and Boot Events

---
entry_id: V2.C2.E041
title: "Kernel-Power 41: The Unexpected Shutdown"
category: event-id
event:
  id: 41
  provider: "Microsoft-Windows-Kernel-Power"
  channel: System
  level: Critical
severity_for_triage: high
applies_to: ["Windows 7+", "Windows Server 2008 R2+"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    path: "windows-client/performance/event-id-41-restart"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `41` is written **at the next boot** when Windows discovers the previous
session did not shut down cleanly. It is a symptom marker, not a cause: it says
"power was lost, the machine hard-hung, or it bugchecked without completing a
clean shutdown." Its BugcheckCode field determines which of those it was.

## Historical / Technical Context
Windows sets a "dirty bit" style flag during normal operation and clears it on
clean shutdown. Kernel-Power checks that flag at boot; if set, it emits 41 and
copies in any bugcheck data preserved from the crash. Introduced with the
Vista/7-era Kernel-Power provider; behavior is unchanged through Windows 11.

## Message Text & Fields
Template (paraphrased): *The system has rebooted without cleanly shutting down
first. This error could be caused if the system stopped responding, crashed, or
lost power unexpectedly.*

| Field | Meaning | Example |
|---|---|---|
| `BugcheckCode` | Decimal stop code of a preceding crash; `0` = no bugcheck recorded | `209` (= `0xD1`) |
| `BugcheckParameter1–4` | The four stop-code parameters | `0x0000000000000008` |
| `SleepInProgress` | Non-zero: failure occurred during a sleep transition | `0` |
| `PowerButtonTimestamp` | Non-zero: power button was held to force off | `0` |
| `CsEntryScenarioInstanceId` | Modern Standby scenario context | `0` |

**Interpretation matrix (original synthesis):**
| BugcheckCode | PowerButtonTimestamp | Reading |
|---|---|---|
| non-zero | 0 | The machine blue-screened — analyze the dump, not event 41 |
| 0 | non-zero | A human held the power button — investigate the *hang* that provoked it |
| 0 | 0 | Sudden power loss or hard hardware hang: PSU, battery, thermal trip, firmware |

## Meaning
41 proves only that the last shutdown was unclean. Everything else comes from
its fields plus surrounding events.

## Likely Root Causes
1. **Preceding bugcheck** — kernel crash; confirming evidence: BugCheck `1001`
   event and a dump in `C:\Windows\Minidump`. *very common*
2. **User-forced power-off during a hang** — PowerButtonTimestamp non-zero;
   look for what was hung (Diagnostics-Performance, app hang 1002). *very common*
3. **Power delivery failure** — desktop PSU, laptop battery/charger, or utility
   loss; no bugcheck, no button timestamp, often clustered under load. *common*
4. **Thermal or hardware protection trip** — CPU/VRM overtemp hard-off; check
   WHEA `17/18/19` events and firmware logs. *common*
5. **Firmware/driver sleep-path defects** — SleepInProgress non-zero; Modern
   Standby transitions are a frequent culprit on laptops. *common*

## Diagnostic Procedure
1. Pull recent 41s with fields:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; Id=41} -MaxEvents 10 |
  ForEach-Object { ([xml]$_.ToXml()).Event.EventData.Data |
    Select-Object Name, '#text' ; '---' }
```
2. Correlate the minute before each 41 across System: look for disk `153`/`129`,
   WHEA errors, or silence (silence = instant power loss).
3. If BugcheckCode ≠ 0, jump to dump analysis (`V3.C2.E002`).
4. Check for held power button and hang evidence if PowerButtonTimestamp ≠ 0.
5. **[MODIFIES SYSTEM]** For suspected sleep-path issues, capture a sleep study:
```cmd
powercfg /sleepstudy /output C:\Diag\sleepstudy.html
```

## Resolution
Keyed to causes: (1) fix per stop code family — see `V2.C13.E002`; (2) resolve
the underlying hang; (3) PSU/battery/cabling replacement or UPS; (4) cooling
remediation, firmware update; (5) update chipset/storage/GPU drivers and BIOS,
consider disabling problematic Modern Standby network activity per vendor guidance.

## Impact
Repeated 41s risk file-system corruption (see NTFS `55`) and data loss;
fleet-wide clusters after a driver rollout are an early rollback signal.

## Related Entries
- V2.C2.E6008 — EventLog 6008 (written for the same unclean shutdown)
- V2.C13.E001b — BugCheck 1001
- V3.C2.E004 — Reading a Kernel Bugcheck Dump

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — Advanced troubleshooting for event ID 41 — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — interpretation matrix and prevalence — License: n/a

---
entry_id: V2.C2.E1074
title: "User32 1074: Who Initiated the Restart"
category: event-id
event:
  id: 1074
  provider: "User32"
  channel: System
  level: Information
severity_for_triage: medium
applies_to: ["Windows XP+", "all supported Server versions"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1074` records every *orderly* shutdown or restart, including the process
that requested it, the user account, the reason code, and any comment. It is
the answer to "who rebooted this server?" and the counterpart that is *absent*
when 41/6008 fire.

## Message Text & Fields
| Field | Meaning | Example |
|---|---|---|
| Process | Image that called the shutdown API | `C:\Windows\System32\MusNotification.exe` |
| User | Account context | `NT AUTHORITY\SYSTEM` |
| Reason / Reason Code | Category from the shutdown-reason table | `Operating System: Upgrade (Planned)` `0x80020003` |
| Shutdown Type | restart / power off / shutdown | `restart` |
| Comment | Free text supplied by the caller | often empty |

Common initiators decoded: `MusNotification.exe`/`svchost (UsoSvc)` = Windows
Update; `CcmExec.exe` = Configuration Manager; `winlogon.exe` + a user account
= interactive Start-menu restart; `wininit.exe` after a bugcheck = automatic
restart following a crash.

## Likely Root Causes
1. **Windows Update maintenance restart** — pairs with update events in Setup
   channel. *very common*
2. **Interactive user restart** — user field is a real account. *very common*
3. **Management tooling** (Intune, ConfigMgr, RMM). *common*
4. **Application-initiated** (installers calling shutdown APIs). *uncommon*

## Diagnostic Procedure
1. List the last 10 initiated shutdowns:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074} -MaxEvents 10 |
  Select-Object TimeCreated, @{n='Msg';e={$_.Message -replace '\r?\n',' | '}} |
  Format-List
```
2. Related IDs to check in the same pass: `1073` (a shutdown was *blocked*),
   `6006` (event log stopped = clean shutdown marker).

## Impact
Establishes accountability for reboots; in incident timelines, 1074 vs. 6008
distinguishes planned maintenance from failure.

## Related Entries
- V2.C2.E6005 — 6005/6006 boot markers
- V2.C2.E041 — Kernel-Power 41

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — shutdown event tracker — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V2.C2.E6005
title: "EventLog 6005/6006: Log Service Start/Stop as Boot Markers"
category: event-id
event:
  id: 6005
  provider: "EventLog"
  channel: System
  level: Information
severity_for_triage: informational
applies_to: ["all supported versions"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`6005` ("The Event log service was started") and `6006` ("…was stopped") are
the classic bookends of a Windows session: 6005 fires early in every boot,
6006 fires during every clean shutdown. Their timestamps let you reconstruct
uptime history from the System log alone.

## Meaning
- 6005 without a preceding 6006 → previous session ended uncleanly (expect a
  `6008` immediately nearby).
- Time between 6006 and the next 6005 → real-world downtime window.
- Companion IDs: `6009` (OS version banner at each boot), `6013` (daily uptime
  report).

## Diagnostic Procedure
1. Build an uptime timeline:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='EventLog'; Id=6005,6006,6008} |
  Select-Object TimeCreated, Id | Sort-Object TimeCreated | Format-Table
```

## Related Entries
- V2.C2.E6008 — the dirty-shutdown record
- V2.C2.E041 — Kernel-Power 41

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C2.E6008
title: "EventLog 6008: The Dirty Shutdown Flag"
category: event-id
event:
  id: 6008
  provider: "EventLog"
  channel: System
  level: Error
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`6008` — "The previous system shutdown at <time> on <date> was unexpected" —
is the legacy sibling of Kernel-Power 41, written by the event log service at
the boot following an unclean stop. Its unique value: it embeds the **last
known timestamp** of the dead session, telling you *when* the machine died,
which 41 does not.

## Meaning
Treat 41 and 6008 as one signal with two views: 41 carries the *why hints*
(bugcheck fields), 6008 carries the *when*. The embedded timestamp is the
event log service's last periodic time record, so the true failure moment is
between that timestamp and the next boot.

## Diagnostic Procedure
1. Extract failure times:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=6008} -MaxEvents 20 |
  Select-Object TimeCreated, Message
```
2. Cross-reference each embedded timestamp against Application/System events in
   the preceding minutes to find the last healthy activity.

## Impact
Same as 41: file-system risk, and the timestamp enables correlation with
facility power records, UPS logs, or user reports.

## Related Entries
- V2.C2.E041 — Kernel-Power 41
- V2.C4.E055 — NTFS 55 corruption follow-up

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C2.E109
title: "Kernel-Power 109: Kernel-Initiated Shutdown"
category: event-id
event:
  id: 109
  provider: "Microsoft-Windows-Kernel-Power"
  channel: System
  level: Information
severity_for_triage: medium
applies_to: ["Windows 8+", "Windows Server 2012+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `109` ("The kernel power manager has initiated a shutdown transition")
marks the kernel itself starting a shutdown. Its `Shutdown Reason` code
distinguishes normal API-driven shutdowns from protective ones — most notably
thermal-initiated emergency shutdowns.

## Meaning
When a machine "just turns off" and 41 shows all-zero fields, a preceding 109
with a thermal reason is the smoking gun for overheating hard-offs. Absence of
109 before an unclean stop points instead to instantaneous power loss.

## Likely Root Causes
1. Normal shutdown path (paired with 1074). *very common*
2. Thermal protection shutdown — check `Kernel-Thermal` / firmware logs,
   clean cooling. *common*
3. Battery-critical action on laptops (power policy critical action). *common*

## Related Entries
- V2.C2.E041 — Kernel-Power 41
- V2.C13.E003 — WHEA-Logger hardware errors

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C2.E142
title: "Kernel-Power 142/506/507: Modern Standby Transitions"
category: event-id
event:
  id: 506
  provider: "Microsoft-Windows-Kernel-Power"
  channel: System
  level: Information
severity_for_triage: medium
applies_to: ["Windows 10+, Modern Standby (S0 Low Power Idle) hardware"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
On Modern Standby laptops, classic sleep events (42/1/107) are joined by S0
low-power-idle records: `506` (entering Modern Standby) and `507` (exiting,
with exit reason such as lid, power button, or wake timer). `142` records a
failed/vetoed transition. These events, with `powercfg /sleepstudy`, are the
basis for diagnosing hot-bag, battery-drain-while-asleep, and wake-failure
complaints.

## Diagnostic Procedure
1. Timeline of standby sessions:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; Id=506,507} -MaxEvents 40 |
  Select-Object TimeCreated, Id, Message
```
2. Identify wake sources and drain offenders:
```cmd
powercfg /sleepstudy /output C:\Diag\sleepstudy.html
powercfg /systemsleepdiagnostics /output C:\Diag\sleepdiag.html
```
3. Check firmware/driver DRIPS blockers listed in the sleep study (network
   drivers and USB devices dominate).

## Likely Root Causes
1. Driver holding activity references (NIC/USB), preventing deepest idle. *very common*
2. Wake timers / scheduled maintenance waking the device in a bag. *common*
3. Firmware defects — fix via OEM BIOS/EC updates. *common*

## Related Entries
- V2.C2.E041 — Kernel-Power 41 (SleepInProgress correlation)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Modern Standby — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — triage guidance — License: n/a
