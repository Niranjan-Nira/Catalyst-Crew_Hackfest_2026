# Volume II · Chapter 6 — System Log: Time, Group Policy, and Directory Client

The domain-membership trio. These three subsystems fail together and blame
each other: broken time breaks Kerberos, broken Kerberos breaks SYSVOL access,
broken SYSVOL access breaks Group Policy — so events here are read as a set,
and the time events are checked *first* whenever authentication-adjacent
errors appear.

---
entry_id: V2.C6.E1058
title: "GroupPolicy 1058/1030: SYSVOL Access Failures"
category: event-id
event: { id: 1058, provider: "Microsoft-Windows-GroupPolicy", channel: System, level: Error }
severity_for_triage: high
applies_to: ["domain-joined machines"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`1058` — "The processing of Group Policy failed. Windows attempted to read the
file \\<domain>\SYSVOL\...\gpt.ini … " (with `1030` as the older/companion
"query for policy objects failed") — means the client could not read a GPO's
files from SYSVOL. GP processing then uses cached policy and retries; the
error names the exact GPO GUID and the failing path, which is the
investigation's starting point.

## Meaning
The embedded error decides the branch: *access denied* → GPO permissions
(Authenticated Users/Domain Computers read rights removed — a classic
self-inflicted wound when "securing" GPOs) or UNC-hardening mismatch; *network
path not found* → DFS/SYSVOL replication or DC reachability; *file not found
for one specific GUID* → that GPO's folder is missing on the answering DC =
SYSVOL replication (DFSR) backlog or damage. One GPO failing vs. all GPOs
failing is the first classification.

## Likely Root Causes
1. **SYSVOL replication (DFSR) issues** — GPO version differs across DCs;
   clients fail depending on which DC answers. *common*
2. **GPO ACL changes** removing computer-read. *common*
3. **UNC hardened paths / SMB signing mismatches** on \\domain\SYSVOL. *common
   since hardening defaults tightened*
4. **General DC reachability** — the Chapter 5719 story wearing GP clothes.
   *common*

## Diagnostic Procedure
1. Identify scope — one GPO or all, one DC or all:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-GroupPolicy'; Id=1058,1030} -MaxEvents 20 |
  Select-Object TimeCreated, Message
gpresult /h C:\Diag\gp.html
```
2. Test the exact path from the event as the *machine* would:
```cmd
dir \\yourdomain.com\SYSVOL\yourdomain.com\Policies\{GUID}\gpt.ini
```
3. Compare GPO versions across DCs (replication check):
```cmd
repadmin /showrepl
dfsrdiag replicationstate
```
   plus `Get-Gpo -Guid <GUID> | Select-Object DisplayName, GpoStatus` for identity.
4. The dedicated GP channel has the full processing narrative:
   `Applications and Services → Microsoft → Windows → GroupPolicy → Operational`
   (event 4016/5016/7016 chains — see V5.C3.E002, queued).

## Impact
Machines silently running stale policy: security settings not applying,
drive maps/printers failing — often discovered only during audits.

## Related Entries
- V2.C5.E5719 — upstream reachability · V2.C6.E129 — time as a hidden cause (Kerberos to SYSVOL)

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — GP processing failures — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — scoping method — License: n/a

---
entry_id: V2.C6.E129
title: "Time-Service 129/134/47/36: The Sync Failure Family"
category: event-id
event: { id: 129, provider: "Microsoft-Windows-Time-Service", channel: System, level: Warning }
severity_for_triage: medium
applies_to: ["all versions; domain semantics on joined machines"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
W32Time's failure vocabulary: `129` — "NtpClient was unable to set a domain
peer to use as a time source because of discovery error… will try again in
<N> minutes" (note the provider-scoped ID collision with storahci 129 —
V2.C4.E129's warning in reverse); `134` — same for a *manually* configured
peer; `47` — unreachable manual peer; `36` — "the time service has not
synchronized … for <N> seconds"; `50` — clock stepped by a large offset
(reading the offset value here explains "why did the clock jump"). Healthy
counterparts: `35/37` (sync established).

## Meaning
Why this matters more than clocks: **Kerberos tolerates ±5 minutes** — beyond
that, authentication fails with `0xC0000133`/KRB skew errors (V2.C9.E4625,
V2.C9.E4768) and everything downstream (SYSVOL, shares, GP) breaks in
confusing ways. Domain hierarchy: members sync from their authenticating DC,
DCs from the PDC emulator, the PDCe from an external source — a broken PDCe
source quietly skews the whole forest. VM nuance: host time integration
services fighting W32Time is a classic dual-source drift generator; pick one
authority.

## Diagnostic Procedure
1. Status triple:
```cmd
w32tm /query /status
w32tm /query /source
w32tm /query /peers
```
   (Source `Local CMOS Clock` or `Free-running System Clock` on a domain
   member = not syncing at all.)
2. Measure actual offset against the domain:
```cmd
w32tm /stripchart /computer:yourdc.yourdomain.com /samples:5 /dataonly
```
3. Event review with the collision-safe filter:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Time-Service'} -MaxEvents 20 |
  Select-Object TimeCreated, Id, Message
```
4. **[MODIFIES SYSTEM]** Reset a member to domain-hierarchy sync:
```cmd
w32tm /config /syncfromflags:domhier /update
w32tm /resync /rediscover
```

## Impact
Time is the silent dependency: a skewed clock produces "certificate not yet
valid," Kerberos failures, and log timelines that can't be correlated — check
it early, not last.

## Related Entries
- V2.C9.E4768 — `0x25` skew code · V2.C12.E008 — time-invalid cert verdicts

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C6.E5722
title: "NETLOGON 5722/3210: Machine Account Password / Secure Channel Failures"
category: event-id
event: { id: 5722, provider: "NETLOGON", channel: System, level: Error }
severity_for_triage: high
applies_to: ["domain-joined machines (5722 logs on the DC; 3210 on the member)"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Every domain computer has its own account with a password rotated
automatically (default every 30 days by the *member*). When member and DC
disagree about that secret, the secure channel fails: the **DC** logs `5722`
("The session setup from the computer <X> failed to authenticate…") and the
**member** logs `3210`/experiences "The trust relationship between this
workstation and the primary domain failed." The dominant cause is state
restoration: snapshots/images/restores rolling a machine back to an old
password after rotation.

## Meaning
What it is not: machine-account passwords do not expire server-side — a PC
left in a closet for a year rejoins fine. The breakage requires *divergence*:
VM snapshot reverts, disk-image redeployment without sysprep, restoring
system-state backups, or duplicate computer names/accounts (two machines
fighting over one account — 5722s alternating sources is that signature).

## Likely Root Causes
1. **VM snapshot/checkpoint revert past a password rotation.** *very common in
   labs and VDI*
2. **Cloned images / duplicate names.** *common*
3. **System-state restore.** *common*
4. **AD-side damage to the computer object (deleted/recreated).** *uncommon*

## Diagnostic Procedure
1. From the member — test and repair the channel *without rejoining*:
```powershell
Test-ComputerSecureChannel -Verbose
```
2. **[MODIFIES SYSTEM]** Repair in place (needs domain credentials; no reboot,
   no profile loss — vastly better than unjoin/rejoin):
```powershell
Test-ComputerSecureChannel -Repair -Credential (Get-Credential)
# or: Reset-ComputerMachinePassword -Server yourdc -Credential (Get-Credential)
# or classic: nltest /sc_reset:yourdomain.com
```
3. On duplicate-name suspicion: check AD for the computer object's
   `pwdLastSet` and lastLogon across suspects; rename one machine.
4. Prevention for virtualization: exclude domain members from long-lived
   snapshots, or disable machine-password change on designated
   revert-heavy lab VMs (policy: *Domain member: Disable machine account
   password changes* — scoped narrowly, never fleet-wide).

## Impact
A broken secure channel blocks GP, domain logons (cached credentials mask it
until they don't), and certificate auto-enrollment; the unjoin/rejoin folk
remedy destroys local profiles unnecessarily — the in-place repair is the
professional fix.

## Related Entries
- V2.C5.E5719 — reachability (different failure, similar wording)
- V2.C9.E4624 — Type 11 cached logons masking the break

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — secure channel troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — divergence framing — License: n/a
