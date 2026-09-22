# Volume V · Chapter 3 — Group Policy

Group Policy still governs most domain-joined fleets. Its failures split into
*processing* problems (the client couldn't apply policy) and *result* problems
(policy applied, but not the one you expected) — different tools for each.

---
entry_id: V5.C3.E001
title: "GP Processing Pipeline and gpresult /h"
category: procedure
severity_for_triage: high
applies_to: ["domain-joined Windows"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
GP processing: the client discovers a DC, reads the list of applicable GPOs
from AD (LDAP), reads each GPO's files from SYSVOL (SMB), and hands settings to
**client-side extensions (CSEs)** that apply them (registry, drive maps,
scripts, security). Foreground processing runs at boot/logon; background
refresh every ~90 minutes (+random offset). The two diagnostic questions —
"did it process?" and "what won?" — have distinct answers.

## Diagnostic Procedure
1. **What won** — the RSoP report (the single best GP diagnostic):
```cmd
gpresult /h C:\Diag\gpresult.html /f
```
   It shows applied GPOs, denied GPOs (and *why* — security filtering, WMI
   filter, disabled link), and per-setting winners. Read the "Denied GPOs"
   section first when an expected policy is missing.
2. **Did it process** — force a refresh with verbose output and read the
   Operational log:
```cmd
gpupdate /force
```
```powershell
Get-WinEvent -LogName 'Microsoft-Windows-GroupPolicy/Operational' -MaxEvents 40 |
  Select-Object TimeCreated, Id, Message
```
3. Scope quickly: `gpresult /r` for a console summary of applied/denied and
   the responsible DC.

## Related Entries
- V5.C3.E002 — the Operational-log event chain · V2.C6.E1058 — SYSVOL failures

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Group Policy processing — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — two-questions framing — License: n/a

---
entry_id: V5.C3.E002
title: "GP Event IDs: The 4000/5000/7000/8000 Operational Chain"
category: event-id
event: { id: 4016, provider: "Microsoft-Windows-GroupPolicy", channel: "Microsoft-Windows-GroupPolicy/Operational", level: Information }
severity_for_triage: medium
applies_to: ["Windows Vista+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Since Vista, GP processing narrates itself in the Operational channel as a
**correlated chain** — every processing instance shares a Correlation
ActivityID, so you can follow one refresh start-to-finish. The bookends:
`4000/4001` policy processing started (computer/user), `8000/8001` completed
successfully (with total time), `7000/7001/7017` completed with *errors*. In
between, `5300`-range informational and `4016/5016/6016/7016` per-CSE
start/success/failure records name which extension took how long or failed.

## Message Text & Fields
| ID range | Meaning |
|---|---|
| 4000/4001 | Processing started (computer/user) |
| 4016 | A CSE started (names the extension, e.g. Registry, Drive Maps, Group Policy Security) |
| 5016 | That CSE succeeded (with elapsed time) |
| 6016/7016 | That CSE returned a warning/error |
| 8000/8001 | Processing completed OK (total elapsed) |
| 7000/7001/7017 | Processing completed with errors / could not apply |
| 5312/5313 | List of applied / denied GPOs for this instance |

## Diagnostic Procedure
1. Follow one processing instance by its Activity ID:
```powershell
$last = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-GroupPolicy/Operational'; Id=4000,4001} -MaxEvents 1
$aid = ([xml]$last.ToXml()).Event.System.Correlation.ActivityID
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-GroupPolicy/Operational'} -MaxEvents 200 |
  Where-Object { ([xml]$_.ToXml()).Event.System.Correlation.ActivityID -eq $aid } |
  Sort-Object TimeCreated | Select-Object TimeCreated, Id, Message
```
2. Slow logon via GP: the 5016 timing events reveal which CSE is slow (drive
   maps against dead servers and printer CSEs against offline print servers
   are classic multi-second stalls — pair with the hang analysis in
   V2.C7.E1002).

## Related Entries
- V5.C3.E001 — gpresult · V5.C3.E003 — the failure causes below

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V5.C3.E003
title: "Common GPO Failures: Slow Link, Loopback, Security Filtering"
category: reference
severity_for_triage: medium
applies_to: ["domain-joined Windows"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
When a policy "doesn't apply," the cause is usually one of a small set of
well-known mechanisms — most of them *policy working as configured*, not a
bug. Knowing the shortlist resolves the majority of GP tickets from the
`gpresult /h` report alone.

## Meaning — the shortlist
| Mechanism | Symptom | How to confirm |
|---|---|---|
| **Security filtering** | GPO denied for this user/computer | gpresult "Denied GPOs" → "Access Denied (Security Filtering)"; check the GPO's Security Filtering + that computers have Read+Apply |
| **WMI filter** | GPO denied to some machines | gpresult "Denied (WMI Filter)"; test the filter's query with `Get-CimInstance` |
| **Loopback processing** | User settings unexpectedly (not) applying on specific machines | Loopback (Merge/Replace) configured on the computer's OU — intended for kiosks/servers, surprising elsewhere |
| **Slow link detection** | Some CSEs skip over slow/VPN links | GP slow-link threshold; certain extensions don't process over slow links by default |
| **Link order / enforcement / block inheritance** | Wrong GPO wins | gpresult precedence order; Enforced links override Block Inheritance |
| **Item-level targeting** (Preferences) | Preference item silently skipped | The item's targeting criteria didn't match |
| **Disabled link or GPO half-disabled** | Whole GPO or its user/computer half inert | GPO status: "User configuration settings disabled" etc. |

## Diagnostic Procedure
1. Start from `gpresult /h` (V5.C3.E001) — the Denied section names the
   mechanism for filtered-out GPOs directly.
2. For "wrong GPO wins," read the precedence list in the report; Enforced and
   link order decide.
3. For Preferences not applying, check item-level targeting in the GPMC
   editor — Preferences fail *silently* by design when targeting doesn't match.
4. Loopback surprises: check the computer's OU for a loopback policy before
   assuming the user policy is broken.

## Related Entries
- V5.C3.E001 — gpresult · V2.C6.E1058 — the SYSVOL-access failure mode

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — GP troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — failure shortlist — License: n/a
