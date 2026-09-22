# Volume IX · Chapter 1 — Slow Boot and Logon Analysis

"It's slow to start" is two different problems — slow *boot* (OS to logon
screen: drivers, services) and slow *logon* (credentials to usable desktop:
profile, GP, scripts, startup apps). Separate them first; the fixes don't
overlap.

---
entry_id: V9.C1.E001
title: "Decomposing Boot: The Free-Tier Method (Diagnostics-Performance)"
category: procedure
severity_for_triage: medium
applies_to: ["Windows Vista+ clients"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Before any tracing, read what Windows already measured. The
Diagnostics-Performance channel (V2.C12.E005) grades every boot and *names the
offenders* — often the whole answer in one query, no WPR required.

## Diagnostic Procedure
1. Get the timing breakdown and trend:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=100} -MaxEvents 20 |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      Boot_s =[int]([int]($d|? Name -eq 'BootTime').'#text'/1000)
      Main_s =[int]([int]($d|? Name -eq 'MainPathBootTime').'#text'/1000)
      Post_s =[int]([int]($d|? Name -eq 'PostBootTime').'#text'/1000) } }
```
2. Interpret the split:
   - High **MainPathBootTime** → drivers/services during core boot; read the
     blame events (101/102/103) next.
   - High **PostBootTime** → startup-app bloat *after* the desktop appears;
     the fix is Autoruns/Startup-apps trimming, not driver work.
3. The blame list — who slowed what:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=101,102,103,106,108,109,110} -MaxEvents 40 |
  Select-Object TimeCreated, Id, Message
```
   (101 app, 102 driver, 103 service, 106 background optimization, 108/109
   device init/degradation.)

## Related Entries
- V2.C12.E005 — the channel · V9.C1.E003 — when this isn't enough

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V9.C1.E002
title: "Slow Logon: Profiles, GP, and Scripts"
category: procedure
severity_for_triage: medium
applies_to: ["domain-joined Windows"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Slow logon (the gap between entering credentials and a usable desktop) is
usually one of four things: a bloated/roaming profile, Group Policy CSEs
stalling on dead resources, logon scripts blocking, or a network dependency
timing out. Each leaves a distinct trace.

## Diagnostic Procedure
1. **Group Policy timing** — which CSE is slow (the 5016 elapsed times):
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-GroupPolicy/Operational'; Id=5016} -MaxEvents 40 |
  Select-Object TimeCreated, Message | Format-List
```
   Drive Maps and Printers CSEs stalling multiple seconds = dead server
   targets (ties to V5.C3.E002 and the hang analysis in V2.C7.E1002).
2. **Profile size/load** — roaming or large local profiles:
```powershell
Get-CimInstance Win32_UserProfile |
  Where-Object { -not $_.Special } |
  Select-Object LocalPath, RoamingConfigured,
    @{n='Size_MB';e={[int]((Get-ChildItem $_.LocalPath -Recurse -File -EA SilentlyContinue |
      Measure-Object Length -Sum).Sum/1MB)}}
```
   Also check User Profile Service events (V2.C8.E1530) for hive-load delays.
3. **Logon scripts / startup**: synchronous logon scripts block the desktop —
   check the *Run logon scripts synchronously* policy and script targets'
   reachability; the User Profile Service and GroupPolicy channels bracket the
   script phase.
4. **The dedicated logon channel**:
   `Microsoft-Windows-User Profile Service/Operational` and
   `Microsoft-Windows-Winlogon/Operational` carry per-phase timings.

## Related Entries
- V5.C3.E002 — GP CSE timing · V2.C8.E1530 — profile events · V2.C7.E1002 — the hang pattern

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V9.C1.E003
title: "Deep Boot Tracing with WPR/WPA"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 8+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
When the free-tier events (E001) point to a phase but not a root cause, boot
tracing captures the whole startup with ETW and lets WPA attribute time to
exact processes, drivers, and I/O. This is the escalation tier — precise, but
with a learning curve.

## Diagnostic Procedure
1. Capture a boot trace (WPR reboots, records, and stops automatically):
```cmd
wpr -boottrace -addboot GeneralProfile -addboot DiskIO -addboot FileIO
:: machine reboots and captures; after it settles:
wpr -boottrace -stopboot C:\Diag\boottrace.etl
```
   (On older setups the ADK's `xbootmgr -trace boot` is the equivalent.)
2. In WPA, load the trace and work the Regions of Interest for boot phases;
   the Boot graphs decompose Pre-Session Init, Session Init, Winlogon Init,
   Explorer Init, Post Boot — you'll see exactly which phase and which
   process/driver dominates.
3. Symbols matter here too (V3.C2.E002) for meaningful stacks.
4. Keep captures targeted — a couple of boots, not a campaign; ETL grows fast.

## Related Entries
- V1.C3.E006 — WPR/WPA/ETW · V9.C1.E001 — the free tier to try first

## References & Attribution
- original synthesis — License: n/a
