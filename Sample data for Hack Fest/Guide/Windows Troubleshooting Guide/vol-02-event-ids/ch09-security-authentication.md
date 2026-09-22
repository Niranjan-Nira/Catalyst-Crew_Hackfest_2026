# Volume II · Chapter 9 — Security Log: Authentication (The 46xx Series)

All events in this chapter: **Channel:** Security · **Provider:**
`Microsoft-Windows-Security-Auditing`. The Security log differs from every
other channel: only LSASS writes to it, events appear only when the matching
audit subcategory is enabled, and `Keywords` (Audit Success / Audit Failure)
replaces Level as the triage axis. IDs here are a stable, Microsoft-controlled
namespace — the closest thing Windows has to a canonical event-ID list.

Enable-state matters: if an event "never occurs," check the policy first:
```cmd
auditpol /get /category:"Logon/Logoff","Account Logon","Account Management"
```

---
entry_id: V2.C9.E4624
title: "4624: Successful Logon (and the Logon Type Table)"
category: event-id
event: { id: 4624, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: medium
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    path: "security/threat-protection/auditing/event-4624"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `4624` — "An account was successfully logged on" — records every
successful logon session creation on the machine where the session was
created. Its **Logon Type** field is the single most important value:
it tells you *how* the credential was used, which separates normal noise from
investigation-worthy access.

## Message Text & Fields
Key fields:
| Field | Meaning |
|---|---|
| Subject | The account that *requested* the logon (often SYSTEM for network logons) — not the user logging on |
| New Logon: Security ID / Account Name / Domain | The account that logged on — the field you care about |
| Logon Type | Numeric type — table below |
| Logon ID | Session identifier (hex) — join key to 4634/4647/4672 and object-access events |
| Elevated Token | Yes = full-admin token session (UAC context) |
| Logon Process / Authentication Package | `NtLmSsp`+NTLM vs. `Kerberos` — protocol used |
| Workstation Name / Source Network Address / Port | Where the request came from — blank/`-` for local |
| Impersonation Level | Delegation potential of the created token |
| Linked Logon ID | Ties the split UAC token pair together |

**The Logon Type table (the core reference):**
| Type | Name | Real-world meaning | Credential exposure on this host |
|---|---|---|---|
| 2 | Interactive | Physical console logon; also `runas` without /netonly | Yes — reusable secrets cached in LSASS |
| 3 | Network | SMB shares, most remote PowerShell/WinRM (default), IIS Windows-auth | No (no reusable creds left behind) |
| 4 | Batch | Scheduled tasks running with stored credentials | Yes |
| 5 | Service | Service start with a logon account | Yes |
| 7 | Unlock | Workstation unlock | Yes (already present) |
| 8 | NetworkCleartext | Network logon where the server received a cleartext password (IIS basic auth) | Password itself crossed the wire to this host |
| 9 | NewCredentials | `runas /netonly` — local identity unchanged, alternate creds for outbound | Alternate creds in LSASS |
| 10 | RemoteInteractive | RDP / Remote Assistance | Yes — RDP without Remote Credential Guard caches creds |
| 11 | CachedInteractive | Interactive logon using cached domain verifier (DC unreachable) | Yes; also tells you the DC was unreachable |
| 12 / 13 | CachedRemoteInteractive / CachedUnlock | Cached variants of 10 / 7 | Yes |
| 0 | System | Machine start system session | n/a |

## Meaning
What 4624 proves: a token/session was created on *this* machine at that time,
via that mechanism. What it does not prove: a human was present (services,
tasks, and machine accounts generate the bulk of 4624 volume — machine
accounts end in `$`).

**Triage heuristics (original synthesis):** Type 3 from unexpected
workstations for admin accounts = lateral-movement review; Type 10 from
unusual source addresses = RDP exposure review; Type 11 spikes = connectivity
problem to DCs, not a security event; ANONYMOUS LOGON 4624s are normal
protocol behavior in moderation.

## Diagnostic Procedure
1. Summarize recent logons by type and account (excluding machine accounts):
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624; StartTime=(Get-Date).AddDays(-1)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      User = ($d | Where-Object Name -eq 'TargetUserName').'#text'
      Type = ($d | Where-Object Name -eq 'LogonType').'#text'
      Src  = ($d | Where-Object Name -eq 'IpAddress').'#text' } } |
  Where-Object User -notlike '*$' |
  Group-Object User, Type | Sort-Object Count -Descending | Select-Object -First 20
```
2. Follow one session end-to-end: take its Logon ID and search 4672 (privileges),
   object access, then 4634/4647 (end) with the same ID.

## Impact
4624 is the backbone of session forensics; its Logon Type column is also a
credential-hygiene map — every Type 2/4/5/10 on a host is a place credentials
can be harvested from LSASS.

## Related Entries
- V2.C9.E4625 — the failure counterpart
- V2.C9.E4672 — privileged session marker
- V2.C9.E4648 — explicit credentials

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — auditing/event-4624 — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — exposure column and heuristics — License: n/a

---
entry_id: V2.C9.E4625
title: "4625: Failed Logon (Status/Sub-Status Decoder)"
category: event-id
event: { id: 4625, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Failure)" }
severity_for_triage: high
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    path: "security/threat-protection/auditing/event-4625"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `4625` — "An account failed to log on" — is the failure mirror of 4624.
Its Failure Reason is rendered text, but the **Status** and **Sub Status**
NTSTATUS codes are the precise diagnosis; Sub Status carries the specific
cause when Status is the generic `0xC000006D` (logon failure).

## Message Text & Fields
**Status / Sub-Status decoder:**
| Code | Meaning | Typical story |
|---|---|---|
| `0xC0000064` | Account does not exist | Typo'd usernames; username spraying |
| `0xC000006A` | Wrong password | The everyday failure; sprays show many accounts × few attempts |
| `0xC000006D` | Generic logon failure (see Sub Status) | Container code |
| `0xC000006E` | Account restriction | Blank password not allowed, workstation restrictions |
| `0xC000006F` | Outside allowed logon hours | Policy working as designed |
| `0xC0000070` | Workstation restriction | Account limited to specific machines |
| `0xC0000071` | Password expired | Users returning from leave; service accounts nobody rotated |
| `0xC0000072` | Account disabled | Attempts against disabled accounts = review source |
| `0xC0000133` | Clock skew too great | Kerberos time drift > 5 min — fix time sync |
| `0xC0000193` | Account expired | Contractor accounts past end date |
| `0xC0000224` | Must change password at next logon | Onboarding friction |
| `0xC0000234` | Account locked out | Follow with 4740 to find the source |
| `0xC00002EE` | Unexpected error during logon | Transient infrastructure issues |
| `0xC0000413` | Authentication firewall (selective auth) | Cross-forest access without permission |

Other high-value fields: Logon Type (same table as 4624 — a failed Type 3 vs.
failed Type 10 tells different stories), Caller Process Name (which local
process submitted the credentials), Workstation Name / Source Network Address.

## Likely Root Causes
1. **Stale stored credentials** — mapped drives, scheduled tasks, mobile
   devices retrying an old password forever; the #1 source of repeated
   `0xC000006A`/lockouts. *very common*
2. **Human error / expired passwords.** *very common*
3. **Brute-force or spray activity** — patterns: one source × many accounts
   (spray) or many passwords × one account (brute force). *common on exposed
   services*
4. **Time skew (`0xC0000133`)** — after VM restores or CMOS battery failure.
   *common*
5. **Misconfigured service/application credentials.** *very common*

## Diagnostic Procedure
1. Failure summary with codes:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625; StartTime=(Get-Date).AddDays(-1)} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      User=($d|? Name -eq 'TargetUserName').'#text'
      Sub =($d|? Name -eq 'SubStatus').'#text'
      Type=($d|? Name -eq 'LogonType').'#text'
      Src =($d|? Name -eq 'IpAddress').'#text'
      Proc=($d|? Name -eq 'ProcessName').'#text' } } |
  Group-Object User, Sub | Sort-Object Count -Descending | Select-Object -First 20
```
2. For lockout chains, pivot to 4740 (V2.C10.E4740) which names the *caller
   computer* — then hunt the stale credential on that machine.
3. Note: domain-account failures may be recorded on the DC (Kerberos 4771 /
   NTLM 4776) rather than, or in addition to, the target machine — check both.

## Impact
Unread 4625 streams hide both operational rot (stale credentials, drift) and
active attacks; the Sub Status column turns the stream into a sorted work
queue.

## Related Entries
- V2.C10.E4740 — lockout source tracing
- V2.C9.E4771 / V2.C9.E4776 — DC-side failure records

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — auditing/event-4625 — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — cause prevalence, hunting patterns — License: n/a

---
entry_id: V2.C9.E4634
title: "4634/4647: Logoff Events"
category: event-id
event: { id: 4634, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: informational
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`4634` — "An account was logged off" — marks session termination for a Logon
ID; `4647` — "User initiated logoff" — is the subset where a human clicked
Sign out (interactive types). Session duration = 4624→4634 delta on the same
Logon ID.

## Meaning
Caveats that save wasted effort: network (Type 3) sessions log off almost
immediately after each operation — thousands of short 4624/4634 pairs are
normal SMB behavior, not churn; missing 4634s happen (fast shutdowns), so
absence of a logoff is weak evidence of a live session.

## Diagnostic Procedure
1. Compute a session's lifetime by Logon ID:
```powershell
$lid = '0x3E7A2'
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624,4634,4647} -MaxEvents 2000 |
  Where-Object { $_.Message -match $lid } | Select-Object TimeCreated, Id
```

## Related Entries
- V2.C9.E4624 — session start

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C9.E4648
title: "4648: Explicit Credential Logon"
category: event-id
event: { id: 4648, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: medium
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `4648` — "A logon was attempted using explicit credentials" — fires when
a process supplies *different* credentials than its own context: `runas`,
scheduled-task credential use, code calling CreateProcessWithLogon/LogonUser,
or outbound connections with alternate accounts. It answers "who used account
B while logged in as account A?"

## Meaning
Fields: Subject (whose session did it), Account Whose Credentials Were Used,
Target Server, Process. Legitimate volume comes from admin tooling and
scheduled tasks. Investigation-worthy: workstation users invoking admin
credentials outside admin workflows, or 4648 chains toward many target servers
in sequence (classic lateral movement with a harvested account).

## Diagnostic Procedure
1. Recent explicit-credential use, subject → target:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4648} -MaxEvents 50 |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      By=($d|? Name -eq 'SubjectUserName').'#text'
      As=($d|? Name -eq 'TargetUserName').'#text'
      To=($d|? Name -eq 'TargetServerName').'#text'
      Proc=($d|? Name -eq 'ProcessName').'#text' } }
```

## Related Entries
- V2.C9.E4624 (Type 9) · V2.C3.E7045 (persistence pairing)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C9.E4672
title: "4672: Special Privileges Assigned"
category: event-id
event: { id: 4672, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success)" }
severity_for_triage: medium
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `4672` — "Special privileges assigned to new logon" — fires alongside a
4624 when the new session's token holds sensitive privileges (SeDebugPrivilege,
SeTcbPrivilege, SeBackupPrivilege, SeImpersonatePrivilege, etc.). Practically:
it flags *admin-equivalent sessions* — the filter that turns a firehose of
4624s into a shortlist.

## Meaning
Match to the 4624 by identical Logon ID. Expect a constant hum of SYSTEM/
service 4672s; the interesting subset is human accounts on machines where they
shouldn't be privileged. A 4672 for a standard user account = someone granted
that account rights — investigate the grant, not just the logon.

## Diagnostic Procedure
1. Privileged human logons today:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4672; StartTime=(Get-Date).Date} |
  ForEach-Object { ([xml]$_.ToXml()).Event.EventData.Data |
    Where-Object Name -eq 'SubjectUserName' } |
  Group-Object '#text' | Where-Object Name -notmatch '\$$|SYSTEM|SERVICE'
```

## Related Entries
- V2.C9.E4624 — the paired session record

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C9.E4768
title: "4768/4769/4771: Kerberos TGT, Service Ticket, and Pre-Auth Failure"
category: event-id
event: { id: 4768, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success/Failure)" }
severity_for_triage: medium
applies_to: ["Domain controllers — Server 2008+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The Kerberos triple, logged **on domain controllers**: `4768` — a TGT was
requested (initial authentication); `4769` — a service ticket was requested
(access to a specific SPN); `4771` — pre-authentication failed (the Kerberos
"wrong password/locked/expired" record). Together they are the DC-side view of
every domain authentication.

## Message Text & Fields
**Result/Failure codes (RFC 4120 codes, hex as logged):**
| Code | Meaning | Story |
|---|---|---|
| `0x6` | Client not found | Nonexistent/deleted account; spraying with bad names |
| `0x12` | Account disabled/expired/locked (revoked) | Follow with 4740 |
| `0x17` | Password expired | Rotation friction |
| `0x18` | Pre-auth failed (wrong password) | The 4771 workhorse — Kerberos twin of `0xC000006A` |
| `0x25` | Clock skew too great | Fix time sync (V2.C6 time entries) |
| Ticket options / encryption type | Requested flags; `0x17` (RC4) etc. | RC4 service-ticket requests from user accounts are a Kerberoasting indicator |

## Meaning
Failed workstation logons for domain accounts often *only* appear on the DC as
4771 — the workstation may log nothing or a sparse 4625. Lockout
investigations and spray detection therefore run on DC logs. 4769 volume is
enormous (every SMB/HTTP/SQL access); mine it for encryption-type anomalies
and unusual SPN access patterns rather than reading it linearly.

## Diagnostic Procedure
1. On a DC — today's pre-auth failures by account and source:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4771; StartTime=(Get-Date).Date} |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ User=($d|? Name -eq 'TargetUserName').'#text'
      Code=($d|? Name -eq 'Status').'#text'
      Src =($d|? Name -eq 'IpAddress').'#text' } } |
  Group-Object User, Code, Src | Sort-Object Count -Descending | Select-Object -First 20
```
2. For lockouts: the 4771 `0x18` stream from one source IP identifies the
   machine holding stale credentials.

## Related Entries
- V2.C9.E4625 — workstation-side view · V2.C10.E4740 — lockout record
- V2.C9.E4776 — the NTLM path

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Kerberos audit events — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — hunting notes — License: n/a

---
entry_id: V2.C9.E4776
title: "4776: NTLM Credential Validation"
category: event-id
event: { id: 4776, provider: "Microsoft-Windows-Security-Auditing", channel: Security, level: "Information (Audit Success/Failure)" }
severity_for_triage: medium
applies_to: ["DCs and any machine validating local accounts"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `4776` — "The computer attempted to validate the credentials for an
account" — is the NTLM analog of 4768/4771: logged on the DC for domain
accounts (pass-through validation) or on the local machine for local accounts.
Error codes reuse the 4625 NTSTATUS family (`0xC000006A` wrong password,
`0xC0000064` no such user, `0xC0000234` locked, `0x0` success).

## Meaning
Two distinct uses: (1) failure streams for lockout/spray tracing when the
client spoke NTLM instead of Kerberos — the Source Workstation field is the
lead; (2) inventorying *who still uses NTLM at all*, feeding NTLM-reduction
projects (pair with the NTLM audit events in
`Microsoft-Windows-NTLM/Operational`, IDs 8001–8004, for full path data).

## Diagnostic Procedure
1. NTLM validation failures by source workstation:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4776; StartTime=(Get-Date).AddDays(-1)} |
  Where-Object { $_.KeywordsDisplayNames -contains 'Audit Failure' } |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ User=($d|? Name -eq 'TargetUserName').'#text'
      Ws =($d|? Name -eq 'Workstation').'#text'
      Err=($d|? Name -eq 'Status').'#text' } } |
  Group-Object User, Ws, Err | Sort-Object Count -Descending
```

## Related Entries
- V2.C9.E4625 · V2.C9.E4768 · V2.C10.E4740

## References & Attribution
- original synthesis — License: n/a
