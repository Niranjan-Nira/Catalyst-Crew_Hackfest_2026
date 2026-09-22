# Volume IV · Chapter 3 — Managed Update Environments

Chapters 1–2 covered the update mechanism on one machine; this chapter covers
the systems that *decide* what a fleet gets — WSUS, Windows Update for
Business, and Autopatch — and how their control planes fail.

---
entry_id: V4.C3.E001
title: "WSUS Troubleshooting"
category: procedure
severity_for_triage: medium
applies_to: ["Windows clients/servers managed by WSUS"]
sources:
  - repo: "MicrosoftDocs/windowsserverdocs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
WSUS problems split cleanly into **client-can't-talk-to-WSUS** and
**WSUS-server-is-unhealthy**. The client side surfaces as the `0x8024xxxx`
family (Chapter 2) pointing at the WSUS URL; the server side shows as declining
performance, the classic huge-catalog timeouts, and the well-known WSUS app-pool
and cleanup issues.

## Diagnostic Procedure
1. Confirm the client's WSUS targeting and last contact:
```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -EA SilentlyContinue |
  Select-Object WUServer, WUStatusServer, TargetGroup, TargetGroupEnabled
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -EA SilentlyContinue |
  Select-Object UseWUServer, NoAutoUpdate
```
   `UseWUServer=1` with an unreachable `WUServer` = the machine won't get
   updates from anywhere (it won't fall back to Microsoft). This is the most
   common "why won't it update" on managed fleets.
2. Force a detect against the server and read the result:
```powershell
(New-Object -ComObject Microsoft.Update.AutoUpdate).DetectNow()
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-WindowsUpdateClient'; Id=20,25,31} -MaxEvents 20 |
  Select-Object TimeCreated, Id, Message
```
3. Server-side classics (WSUS admin): the IIS **WsusPool** app pool
   recycling/stopping under memory pressure (raise the private-memory limit
   or set it to 0), and skipped maintenance — declining superseded updates and
   running the cleanup wizard/reindex, without which clients hit
   `0x80244010` (too many round trips) against a bloated catalog (Chapter 2).
4. Reset a stuck client's state per V4.C2.E006 only after confirming the
   targeting/reachability is correct.

## Related Entries
- V4.C2.E002 — the 0x8024 codes clients report · V4.C2.E006 — client reset

## References & Attribution
- MicrosoftDocs/windowsserverdocs — WSUS troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — client-vs-server split, app-pool note — License: n/a

---
entry_id: V4.C3.E002
title: "Windows Update for Business / Autopatch"
category: concept
severity_for_triage: medium
applies_to: ["Windows 10/11 managed via Intune/policy"]
sources:
  - repo: "MicrosoftDocs/memdocs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Windows Update for Business (WUfB) manages updates via policy (deferrals,
deadlines, rings) while payloads still come from Microsoft's CDN — no
on-prem infrastructure. **Autopatch** builds on WUfB to automate ring
assignment, deployment, and reporting. Troubleshooting is mostly "why isn't
this device in the state the policy intends" — an *offering/eligibility*
question, not a download failure.

## Meaning — the frequent confusions
- **Dual scan** conflicts: a device pointed at WSUS (`UseWUServer=1`) *and*
  given WUfB policies gets contradictory instructions — a top cause of
  "policies ignored." Pick one authority.
- **Safeguard holds**: WUfB honors Microsoft's compatibility holds; a device
  legitimately not offered a feature update may be held, not broken — don't
  force past holds on production.
- **Deadline/deferral interplay**: deadlines override deferrals; a
  "surprise" reboot is usually a deadline reached, visible in policy state.
- **Reporting lag**: Autopatch/WUfB reports aggregate with delay; a device can
  be healthy before the dashboard shows it.

## Diagnostic Procedure
1. Read the effective update policy the device actually has:
```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\PolicyManager\current\device\Update' -EA SilentlyContinue |
  Select-Object DeferQualityUpdatesPeriodInDays, DeferFeatureUpdatesPeriodInDays,
    PauseQualityUpdates*, DeadlineForQualityUpdates*, BranchReadinessLevel
```
2. Confirm no dual-scan conflict:
```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -Name UseWUServer -EA SilentlyContinue
```
   (Present + WUfB policies = investigate dual scan first.)
3. Client-side update events and the ETW log (Chapter 2) show what was offered
   and when; tenant-side reporting shows intended state — reconcile the two.

## Related Entries
- V4.C1.E004 — servicing channels/deferral · V4.C3.E001 — the dual-scan other half

## References & Attribution
- MicrosoftDocs/memdocs — WUfB / Autopatch — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — confusion list — License: n/a

---
entry_id: V4.C3.E003
title: "Expedited Updates and Compliance Deadlines"
category: concept
severity_for_triage: low
applies_to: ["Windows 10/11 via Intune"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
**Expedited updates** push a specific critical fix to devices out-of-band,
bypassing normal deferrals via a dedicated policy path (using the update
health tools/agent) so an emergency patch lands in hours, not rings.
**Compliance deadlines** force install+reboot after a grace period once an
update is applicable. Both are "why did this device patch/reboot now?"
answers.

## Diagnostic Procedure
1. Deadline state and pending reboot:
```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -EA SilentlyContinue |
  Select-Object *Deadline*, PendingRebootStartTime -EA SilentlyContinue
Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
```
2. Expedited delivery relies on the update health tools agent; if expedited
   updates never arrive, verify that agent's presence/health and the device's
   Intune connectivity (V5.C2.E001).
3. Correlate the resulting reboot with User32 1074 (V2.C2.E1074) — the
   initiator/reason there confirms an update-driven restart.

## Related Entries
- V2.C2.E1074 — who initiated the reboot · V5.C2.E001 — Intune connectivity

## References & Attribution
- original synthesis — License: n/a
