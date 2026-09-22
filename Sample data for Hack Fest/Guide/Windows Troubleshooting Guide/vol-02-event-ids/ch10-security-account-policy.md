# Volume II · Chapter 10 — Security Log: Account and Policy Management

Same channel/provider conventions as Chapter 9. These events audit *changes to
the security fabric itself* — accounts, groups, lockouts, audit policy, and
the log. They are low-volume and high-signal: nearly every one deserves to be
attributable to a known process (joiner/mover/leaver workflow, admin change
ticket) — the unattributable remainder is your review queue.

---
entry_id: V2.C10.E4720
title: "4720–4726: Account Lifecycle"
category: event-id
event: { id: 4720, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: medium
applies_to: ["Windows Vista+/Server 2008+ (DCs for domain accounts; members for local accounts)"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The account lifecycle set: `4720` created · `4722` enabled · `4723` password
change attempted (by the user) · `4724` password *reset* attempted (by an
admin/other) · `4725` disabled · `4726` deleted. Subject = who performed the
action; Target = the account acted upon.

## Meaning
The 4723-vs-4724 distinction matters: 4723 is a user changing their own
password (knows the old one); 4724 is a reset by someone else — helpdesk flow
or account-takeover step. A 4720 followed minutes later by group additions
(4728/4732) and then 4726 deletion is the burn-after-use pattern: temporary
account creation worth alerting on.

**Local accounts note:** these IDs fire on the *member machine* for local
accounts — a 4720 on a workstation means someone created a local account
there, which modern management (LAPS-only philosophy) usually forbids.

## Diagnostic Procedure
1. Account changes with subject/target extraction:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4720,4722,4723,4724,4725,4726; StartTime=(Get-Date).AddDays(-7)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated; Id=$_.Id
      By=($d|? Name -eq 'SubjectUserName').'#text'
      On=($d|? Name -eq 'TargetUserName').'#text' } }
```
2. Reconcile against the change process (tickets/IGA) — the residual is the
   finding.

## Related Entries
- V2.C10.E4728 — group changes · V2.C9.E4624 — first logon of a new account

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — account management auditing — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — burn-after-use pattern — License: n/a

---
entry_id: V2.C10.E4728
title: "4728/4732/4756: Group Membership Changes"
category: event-id
event: { id: 4732, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: high
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Member-added events by group scope: `4728` global · `4732` domain-local /
machine-local · `4756` universal (removals: `4729`/`4733`/`4757`). The one
alert every environment should run: additions to Tier-0 groups — Domain
Admins, Enterprise Admins, Administrators, plus your crown-jewel app groups.

## Meaning
Fields: Subject (who added), Member (who was added — logged as SID and
distinguished name), Group. On workstations/servers, 4732 into local
`Administrators` is the local-priv-esc audit trail. Empty/unresolvable Member
name with only a SID often indicates a cross-domain principal — resolve the
SID before judging.

## Diagnostic Procedure
1. Sensitive-group additions in the last 30 days:
```powershell
$groups = 'Domain Admins','Enterprise Admins','Administrators','Schema Admins'
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4728,4732,4756; StartTime=(Get-Date).AddDays(-30)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      Group =($d|? Name -eq 'TargetUserName').'#text'
      Member=($d|? Name -eq 'MemberName').'#text'
      By    =($d|? Name -eq 'SubjectUserName').'#text' } } |
  Where-Object Group -in $groups
```

## Related Entries
- V2.C10.E4720 — lifecycle pairing · V2.C9.E4672 — resulting privileged logons

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C10.E4740
title: "4740: Account Lockout"
category: event-id
event: { id: 4740, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: high
applies_to: ["Logged on the PDC emulator for domain accounts; locally for local accounts"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `4740` — "A user account was locked out" — is the definitive lockout
record, and its **Caller Computer Name** field is the treasure: the machine
from which the final bad attempt came. For domain accounts, lockout processing
converges on the **PDC emulator**, so query 4740 there, not on random DCs.

## Meaning
4740 tells you *which machine* to search; it does not tell you *which process*
on that machine holds the stale credential. The follow-up hunt on the named
machine covers the usual suspects, in prevalence order: saved credentials in
Credential Manager, mapped drives, scheduled tasks, services with logon
accounts, mobile devices with cached mail (mail-client retries lock accounts
constantly), disconnected-but-alive RDP sessions elsewhere, and IIS app pools.
An empty/`-` Caller Computer usually means a network-protocol path (e.g.,
NTLM via a proxy) — pivot to the 4771/4776 failure stream on the DCs for the
source IP instead.

## Diagnostic Procedure
1. On the PDC emulator — recent lockouts with sources:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4740; StartTime=(Get-Date).AddDays(-2)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      User  =($d|? Name -eq 'TargetUserName').'#text'
      Caller=($d|? Name -eq 'TargetDomainName').'#text' } }
```
   (Field layout note: in 4740 the caller computer arrives in the
   `TargetDomainName` data slot — verify against your build with the XML view.)
2. On the caller machine, sweep the stale-credential suspects:
```cmd
cmdkey /list
schtasks /query /fo LIST /v | findstr /i "Run As User"
```
```powershell
Get-CimInstance Win32_Service | Where-Object StartName -like '*<user>*' |
  Select-Object Name, StartName
```
3. Correlate with the 4771 `0x18` / 4776 `0xC000006A` stream to see the retry
   cadence (regular intervals = automated process, human-typing bursts = human).

## Resolution
Remove/refresh the stale credential at the identified source; unlock; confirm
the failure stream stops. Recurring lockouts with rotating callers = spray —
shift to security response.

## Impact
Lockout storms are both a denial-of-service on real users and the most common
"security incident" that turns out to be a forgotten scheduled task.

## Related Entries
- V2.C9.E4625 · V2.C9.E4771 · V2.C9.E4776

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — account lockout troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — suspect prevalence order — License: n/a

---
entry_id: V2.C10.E4719
title: "4719: System Audit Policy Was Changed"
category: event-id
event: { id: 4719, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: high
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `4719` — "System audit policy was changed" — records every modification
to what gets audited: category/subcategory and the change (success/failure
auditing added or removed). Legitimate sources: GPO refreshes applying
baseline policy. Illegitimate: an intruder switching off the cameras before
acting.

## Meaning
The event's Subject for GPO-driven changes is typically SYSTEM — what
distinguishes benign from hostile is *what changed* and *whether it matches
policy*: removal of auditing on Logon, Account Management, or Object Access
subcategories outside a change window is a top-tier alert. Repeated flapping
(same subcategory toggling every refresh) instead indicates conflicting GPOs
vs. local `auditpol` settings — an ops problem masquerading as noise.

## Diagnostic Procedure
1. What does effective policy say right now:
```cmd
auditpol /get /category:*
```
2. Recent policy changes:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4719} -MaxEvents 20 |
  Select-Object TimeCreated, Message | Format-List
```
3. For flapping: compare GPO advanced audit settings against local basic
   audit settings — mixing the two regimes causes the oscillation; standardize
   on Advanced Audit Policy and enable the "force subcategory settings"
   security option.

## Related Entries
- V2.C10.E1102 — the companion "cameras off" event
- V6.C1.E002 — audit policy design (queued)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C10.E1102
title: "1102: The Audit Log Was Cleared"
category: event-id
event: { id: 1102, provider: "Microsoft-Windows-Eventlog", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: high
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `1102` — "The audit log was cleared" — is written *into the freshly
cleared Security log* as its first entry, naming the account that cleared it.
It cannot be suppressed by the clearing action itself; that is by design.
(The System log analog for other logs is `104`, provider
`Microsoft-Windows-Eventlog`.)

## Meaning
There are few legitimate reasons to clear a Security log (size management is
done by retention policy, not clearing). Every 1102 deserves attribution to a
person and a reason. In incident response, a 1102 timestamp is a pivot: it
marks "evidence destruction time" — collect forwarded copies (WEF/SIEM) for
the destroyed window and treat the clearing account as compromised until
explained.

## Diagnostic Procedure
1. Check for clears across the estate (Security 1102 and System 104):
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=1102} -MaxEvents 5 |
  Select-Object TimeCreated, Message
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Eventlog'; Id=104} -MaxEvents 10 |
  Select-Object TimeCreated, Message
```
2. Mitigation posture: forward Security events off-box (Windows Event
   Forwarding or SIEM agent) so clearing the local log destroys nothing.

## Related Entries
- V2.C10.E4719 — audit policy tampering

## References & Attribution
- original synthesis — License: n/a
