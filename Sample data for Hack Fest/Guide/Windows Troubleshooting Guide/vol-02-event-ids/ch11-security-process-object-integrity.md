# Volume II · Chapter 11 — Security Log: Process, Object, and System Integrity

Channel/provider conventions as Chapters 9–10. This chapter's events are
**mostly off by default** and **high-volume when on** — they are enabled
deliberately, for detection and forensics, and tuned to avoid drowning the
log. Each entry notes the audit subcategory that produces it and the
volume-control reality.

---
entry_id: V2.C11.E4688
title: "4688: Process Creation (with Command-Line Auditing)"
category: event-id
event: { id: 4688, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: medium
applies_to: ["Windows Vista+; command line since 8.1/Server 2012 R2 + policy"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`4688` — "A new process has been created" — is, with command-line auditing
enabled, the single most valuable detection event in Windows: it records the
new process, its **full command line**, the parent process, the account, and
(newer builds) the parent-image path and token elevation type. Subcategory:
*Detailed Tracking → Audit Process Creation*; command line requires the
additional policy *Include command line in process creation events*.

## Message Text & Fields
| Field | Meaning | Why it matters |
|---|---|---|
| New Process Name | Image path of the child | What ran |
| Process Command Line | Full arguments (policy-gated) | The actual behavior — `powershell -enc <base64>`, `rundll32` abuse, LOLBins |
| Creator Process Name / New Process Id / Creator Process Id | Parent chain | Anomalous parents (Office spawning cmd, `w3wp` spawning shells) |
| Token Elevation Type | %%1936/1937/1938 = full/limited/default | Elevation context |
| SubjectUserName | Who | Attribution |

## Meaning
The parent-child relationship is the detection substrate: `winword.exe →
cmd.exe → powershell.exe` is a phishing macro's fingerprint; `services.exe →`
an unknown binary in TEMP is service-based execution. Command-line arguments
turn generic binaries (rundll32, mshta, regsvr32, certutil — the "LOLBins")
from invisible to obvious. **Sensitivity note:** command lines can capture
secrets typed as arguments — treat the Security log's confidentiality
accordingly.

## Diagnostic Procedure
1. Confirm auditing is actually capturing command lines:
```cmd
auditpol /get /subcategory:"Process Creation"
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit" /v ProcessCreationIncludeCmdLine_Enabled
```
2. Hunt anomalous parentage / LOLBins:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4688; StartTime=(Get-Date).AddHours(-24)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      Parent=($d|? Name -eq 'ParentProcessName').'#text'
      Proc  =($d|? Name -eq 'NewProcessName').'#text'
      Cmd   =($d|? Name -eq 'CommandLine').'#text' } } |
  Where-Object { $_.Proc -match 'powershell|cmd|rundll32|mshta|regsvr32|certutil|wscript|cscript' }
```
3. Volume reality: 4688 is high-rate on busy hosts. Central collection with
   filtering (WEF/SIEM) beats local retention; scope local audit to endpoints
   that warrant it.

## Related Entries
- V2.C12.E003 — PowerShell 4104 (the content behind the command line)
- V2.C11.E4697 — service-install counterpart

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — event 4688 & command-line auditing — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — parentage detection patterns — License: n/a

---
entry_id: V2.C11.E4663
title: "4656/4658/4660/4663: Object Access"
category: event-id
event: { id: 4663, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success/Failure)" }
severity_for_triage: medium
applies_to: ["Windows Vista+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The object-access quartet fires only when *both* the audit subcategory
(*Object Access → Audit File System / Registry / etc.*) **and** a SACL on the
specific object are configured — a deliberate, two-key design that keeps this
otherwise ruinous-volume auditing targeted. `4656` handle requested (with the
access mask), `4663` an access was **actually performed** (the mask shows
what — read/write/delete), `4660` object **deleted**, `4658` handle closed.

## Meaning
`4656` = intent (a handle was asked for, possibly denied — Audit Failure 4656
catches access-denied attempts on watched objects); `4663` = action (the
operation happened). The AccessMask is the detail: `0x2`/`0x4` write/append,
`0x10000` DELETE, `0x1` read. Practical use: SACL a sensitive folder or a
registry Run key, audit for writes, and 4663 becomes a change-detection feed
for exactly that object without auditing the whole disk.

## Diagnostic Procedure
1. Set a targeted SACL (example: audit writes to a Run key) —
   **[MODIFIES SYSTEM]**, via `wevtutil`/`Set-Acl`/GUI; then confirm events:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4663; StartTime=(Get-Date).AddDays(-1)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      Obj =($d|? Name -eq 'ObjectName').'#text'
      By  =($d|? Name -eq 'SubjectUserName').'#text'
      Mask=($d|? Name -eq 'AccessMask').'#text' } }
```
2. Decode the mask in the event's own "Accesses" rendered list rather than
   memorizing hex.

## Related Entries
- V2.C10.E4719 — auditing this requires policy on

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C11.E5140
title: "5140/5145: Network Share Access"
category: event-id
event: { id: 5140, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success/Failure)" }
severity_for_triage: medium
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`5140` — "A network share object was accessed" — logs each connection to a
share (who, from which source IP, which share); `5145` — the *detailed*
file-share access with per-file access checks (very high volume — enable only
for targeted investigations); `5142/5143/5144` — share created/modified/
deleted. Subcategory: *Object Access → Audit File Share* (5140) and
*Detailed File Share* (5145).

## Meaning
5140 answers "who is hitting SYSVOL/NETLOGON/a data share and from where" —
useful for both access review and spotting anomalous lateral SMB (a
workstation IP connecting to admin shares). The `\\*\IPC$` and `\\*\ADMIN$`
connections in 5140 are the SMB substrate of remote administration and
remote-exec tools; their source IPs are the lead. 5145's per-file granularity
is for "prove exactly which files this account touched" forensics — not
routine monitoring.

## Diagnostic Procedure
1. Share connections by source and target:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=5140; StartTime=(Get-Date).AddHours(-12)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      Share=($d|? Name -eq 'ShareName').'#text'
      Src  =($d|? Name -eq 'IpAddress').'#text'
      By   =($d|? Name -eq 'SubjectUserName').'#text' } } |
  Group-Object Share, Src | Sort-Object Count -Descending | Select-Object -First 20
```
2. Pair suspicious admin-share access with 4624 Type 3 (V2.C9.E4624) from the
   same source to build the session picture.

## Related Entries
- V2.C9.E4624 — the logon behind the share access

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C11.E4697
title: "4697: Service Installation (Security-Log Counterpart of 7045)"
category: event-id
event: { id: 4697, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: medium
applies_to: ["Windows 10/Server 2016+ (subcategory-audited)"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`4697` — "A service was installed in the system" — is the *audited* twin of
System-log 7045 (V2.C3.E7045): same event class, richer subject data (the
account that installed it, with full token context), and it lands in the
Security log where tamper-resistance and forwarding are stronger. Subcategory:
*System → Audit Security System Extension*.

## Meaning
Prefer 4697 over 7045 when available: the Security log is harder to clear
without leaving 1102 (V2.C10.E1102), is centrally forwarded in mature
environments, and 4697 attributes the install to a *principal*, not just
records that it happened. Same hunting heuristics as 7045: image paths in
TEMP/user-profiles, command interpreters as the service binary, random names.

## Diagnostic Procedure
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4697} -MaxEvents 30 |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      Svc =($d|? Name -eq 'ServiceName').'#text'
      File=($d|? Name -eq 'ServiceFileName').'#text'
      By  =($d|? Name -eq 'SubjectUserName').'#text' } }
```

## Related Entries
- V2.C3.E7045 — the System-log sibling · V2.C12.E001 — scheduled-task persistence (4698)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C11.E6416
title: "6416: A New External Device Was Recognized"
category: event-id
event: { id: 6416, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: medium
applies_to: ["Windows 10/Server 2016+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`6416` — "A new external device was recognized by the system" — audits
plug-and-play device arrivals (device class, instance ID, vendor/product) in
the Security log; `6419/6420/6421/6422/6423/6424` cover
disable/removal-request lifecycle. Subcategory: *Detailed Tracking → Audit PNP
Activity*. This is the audit trail for removable-media governance and the
"what got plugged into this machine" question.

## Meaning
The instance ID and class GUID identify the device type and often the specific
hardware; correlate with the operational Kernel-PnP channel (V2.C12.E007) for
the driver-load side. Use cases: USB storage governance (pair with device
control policy), spotting unexpected HID/network devices (rubber-ducky-class
attack hardware announces itself here), and asset tracking. Note this audits
recognition, not data transfer — content-level DLP is a separate control.

## Diagnostic Procedure
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=6416} -MaxEvents 40 |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      Class=($d|? Name -eq 'ClassName').'#text'
      Dev  =($d|? Name -eq 'DeviceId').'#text' } }
```

## Related Entries
- V2.C12.E007 — Kernel-PnP operational side · V6.* — device control (queued)

## References & Attribution
- original synthesis — License: n/a
