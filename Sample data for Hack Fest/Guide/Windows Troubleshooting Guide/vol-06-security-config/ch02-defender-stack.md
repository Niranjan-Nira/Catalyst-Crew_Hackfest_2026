# Volume VI · Chapter 2 — The Defender Stack

Microsoft Defender is several products under one name: the antivirus engine,
the host firewall, SmartScreen reputation, and Exploit Protection. This
chapter covers their configuration and the operational events that reveal
whether they're working — and when they're the *cause* of a problem.

---
entry_id: V6.C2.E001
title: "Microsoft Defender Antivirus Configuration and Ops Events"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11, Server 2016+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The `Get-Mp*` cmdlets and the `Microsoft-Windows-Windows Defender/Operational`
channel (V2.C12.E002) together answer every Defender question: is it running
and current, what has it detected, what's excluded, and — crucially for
performance tickets — is *it* the reason a machine is slow.

## Meaning
Two troubleshooting realities dominate:
1. **Passive/EDR-block mode confusion:** when a third-party AV is present,
   Defender AV runs in passive mode (`AMRunningMode`) — real-time protection
   is off by design; "Defender isn't protecting" is expected, not broken.
   `Get-MpComputerStatus` `AMRunningMode` tells you: Normal, Passive, EDR
   Block, or SxS Passive.
2. **Defender as the performance culprit:** real-time scanning of build
   directories, database files, dev toolchains, or backup jobs causes high CPU
   in `MsMpEng.exe`. The fix is *correct exclusions*, not disabling protection
   — and exclusions themselves are audited (5007), so overly broad exclusions
   are both a performance hack and a security hole to review.

## Diagnostic Procedure
1. Posture and mode:
```powershell
Get-MpComputerStatus | Select-Object AMRunningMode, RealTimeProtectionEnabled,
  AntivirusEnabled, AntivirusSignatureLastUpdated, NISEnabled, IsTamperProtected
```
2. Detections and exclusions:
```powershell
Get-MpThreatDetection | Select-Object -First 10 ThreatID, InitialDetectionTime, Resources
Get-MpPreference | Select-Object ExclusionPath, ExclusionProcess, ExclusionExtension
```
3. Performance analysis — measure what real-time scanning costs, per path:
```powershell
New-MpPerformanceRecording -RecordTo C:\Diag\defender.etl   # reproduce load, Ctrl-C
Get-MpPerformanceReport -Path C:\Diag\defender.etl -TopFiles 20 -TopPaths 20
```
   This names the exact files/paths costing scan time — the evidence for a
   targeted exclusion.
4. Tamper Protection note: when on, some settings can't be changed by scripts/
   local admin (by design) — changes must come through the management channel;
   "my exclusion won't apply" often means Tamper Protection, not a bug.

## Related Entries
- V2.C12.E002 — Defender events · V6.C1.E006 — ASR rules

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Defender AV management / performance analyzer — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — passive-mode and performance framing — License: n/a

---
entry_id: V6.C2.E002
title: "Defender Firewall: Profiles, Rules, and Log Analysis"
category: procedure
severity_for_triage: high
applies_to: ["Windows 7+/Server 2008 R2+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
"The app can't connect" and "the firewall is blocking it" are among the most
common — and most misdiagnosed — tickets. The host firewall applies rules per
**profile** (Domain / Private / Public), and the single most frequent surprise
is a machine on the wrong profile (Public on a network that should be Domain),
where stricter rules apply. Rule evaluation, profile detection, and the
dropped-packet log are the three things to read.

## Meaning
- **Profile mismatch:** if the network isn't identified as Domain (NLA can't
  reach a DC), the machine falls to Public and blocks things Domain would
  allow — a networking problem masquerading as a firewall problem (ties to
  V2.C5/C6 DC reachability).
- **Block precedence:** an explicit block rule beats any allow; a missing
  allow rule blocks by default inbound. The winning rule is findable.
- **Merge behavior:** GPO firewall rules merge with (or replace) local rules
  depending on policy — "my local allow rule does nothing" is often GPO
  disabling local rule merge.

## Diagnostic Procedure
1. Which profile is active, and is it the expected one:
```powershell
Get-NetConnectionProfile | Select-Object InterfaceAlias, NetworkCategory
Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction
```
2. Find rules affecting a port/app:
```powershell
Get-NetFirewallRule -Enabled True |
  Where-Object { ($_ | Get-NetFirewallPortFilter).LocalPort -eq 445 } |
  Select-Object DisplayName, Direction, Action, Profile
```
3. **[MODIFIES SYSTEM]** Enable the dropped-packet log to *prove* a block:
```powershell
Set-NetFirewallProfile -All -LogBlocked True -LogFileName '%SystemRoot%\System32\LogFiles\Firewall\pfirewall.log'
# reproduce, then read:
Get-Content $env:SystemRoot\System32\LogFiles\Firewall\pfirewall.log -Tail 40
```
   A DROP line with the port/IP is definitive proof it's the firewall; its
   absence redirects you elsewhere (the app, routing, the *remote* firewall).

## Impact
Misattributed firewall tickets waste time on both ends; the dropped-packet log
ends the "is it the firewall?" debate in one step.

## Related Entries
- V2.C5.* — networking events · V6.C2.E001 — Defender AV

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Windows Firewall — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — profile-mismatch and proof-via-log framing — License: n/a

---
entry_id: V6.C2.E003
title: "SmartScreen and Exploit Protection"
category: concept
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Two more Defender-family controls that generate support cases. **SmartScreen**
is reputation-based blocking of files/URLs/apps (the "Windows protected your
PC" prompt on unrecognized installers). **Exploit Protection** is the
successor to EMET — process-level mitigations (DEP, ASLR, CFG, and more)
applied system-wide or per-app, which can break applications incompatible with
a specific mitigation.

## Meaning
- **SmartScreen** troubleshooting: internally-distributed but unsigned apps
  trip it constantly ("unrecognized" ≠ "malicious" — it means low
  reputation). Code-signing with a reputable cert builds reputation; policy
  can tune the prompt. The Application-Reputation events and the App & Browser
  Control settings are the surface.
- **Exploit Protection** troubleshooting: when a specific app crashes only
  with mitigations on, a per-app mitigation is the culprit. Events land in
  `Microsoft-Windows-Security-Mitigations/*` and
  `Microsoft-Windows-Win32k/Operational`; the fix is a per-app mitigation
  exception, not disabling protection system-wide.

## Diagnostic Procedure
1. Read/adjust exploit-protection mitigations:
```powershell
Get-ProcessMitigation -System | Select-Object -First 5
Get-ProcessMitigation -Name vulnerable-app.exe
```
2. Check the mitigations event channel when an app crashes under protection:
```powershell
Get-WinEvent -LogName 'Microsoft-Windows-Security-Mitigations/KernelMode' -MaxEvents 20 -EA SilentlyContinue |
  Select-Object TimeCreated, Id, Message
```
3. **[MODIFIES SYSTEM]** Apply a per-app exception rather than a global
   rollback (example: disable a single mitigation for one app):
```powershell
Set-ProcessMitigation -Name legacy-app.exe -Disable ForceRelocateImages
```
4. Correlate app crashes (V2.C7.E1000) that appear only after enabling
   exploit protection — the mitigation events name which check fired.

## Related Entries
- V2.C7.E1000 — the crashes mitigations can cause · V3.C1.E006 — BEX/0xC0000409 (mitigation-adjacent codes)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — SmartScreen / Exploit Protection — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — per-app exception discipline — License: n/a
