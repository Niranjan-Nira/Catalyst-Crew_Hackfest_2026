# Volume VI · Chapter 1 — Baseline Hardening

Security configuration is troubleshooting's mirror image: the same events and
subsystems, read for "is this control working and correctly scoped?" instead
of "why did this break?" Every hardening control in this chapter also *causes*
support cases when misapplied — each entry notes both sides.

---
entry_id: V6.C1.E001
title: "Microsoft Security Baselines and LGPO"
category: concept
severity_for_triage: informational
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
A **security baseline** is Microsoft's recommended set of policy settings for
a Windows version, shipped in the **Security Compliance Toolkit** (SCT) as GPO
backups, spreadsheets of every setting, and the **LGPO.exe** tool for applying
policy to standalone machines. Baselines are the starting point most
enterprises tailor rather than the finish line.

## Meaning
Components: the GPO backups (import into AD or apply locally), the
documentation workbook (the authoritative "what does this baseline set and
why"), Policy Analyzer (diff baselines against each other or against a live
machine — the tool for "what did upgrading the baseline change"), and LGPO
(scriptable local policy for non-domain/imaging scenarios). Baselines version
with the OS; applying a Windows 10 baseline to Windows 11 leaves new settings
unmanaged.

The troubleshooting flip side: baselines are the *cause* of many "it worked
before hardening" tickets — restrictive settings around NTLM, SMB signing,
UAC, LSA protection, and legacy protocol removal break old apps. Policy
Analyzer's diff is the first tool when a baseline update coincides with new
failures.

## Diagnostic Procedure
1. Diff what a baseline would change vs. current state with Policy Analyzer
   (GUI), or read effective policy directly:
```cmd
gpresult /h C:\Diag\gp.html
auditpol /get /category:*
```
2. Apply/test local policy from a baseline with LGPO:
```cmd
LGPO.exe /g .\GPOBackup   :: apply
LGPO.exe /parse /m registry.pol   :: read what a .pol contains
```
3. When a baseline update breaks an app, diff old vs. new baseline in Policy
   Analyzer to find the responsible setting rather than reverting wholesale.

## Related Entries
- V2.C10.E4719 — audit policy the baseline sets · V5.C3 — GP processing (queued)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — security baselines / SCT — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — baseline-as-cause framing — License: n/a

---
entry_id: V6.C1.E002
title: "Audit Policy Design (What to Enable and Why)"
category: procedure
severity_for_triage: informational
applies_to: ["Windows Vista+/Server 2008+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The Security log is only as useful as the audit policy feeding it — the entire
Chapters 9–11 of Volume II are inert without the right subcategories enabled,
and *over*-auditing drowns signal and wraps the log before an incident is
noticed. Design is choosing the high-value subcategories and controlling
volume.

## Meaning — the high-value shortlist
| Subcategory | Yields | Volume |
|---|---|---|
| Logon / Logoff | 4624/4625/4634 | High — but essential |
| Account Lockout | 4740 | Low, essential |
| Account Management | 4720–4726, 4728/4732 | Low, essential |
| Security Group Management | group changes | Low, essential |
| Process Creation (+ cmdline) | 4688 | **Very high** — central-collect, scope carefully |
| Audit Policy Change | 4719 | Low, essential (tamper) |
| Security System Extension | 4697 | Low, high-value (persistence) |
| Special Logon | 4672 | Medium |
| Kerberos/Credential Validation (DCs) | 4768/4769/4771/4776 | Very high on DCs |
| PNP Activity | 6416 | Low-medium |
| File System / Registry (Object Access) | 4663 | **Ruinous without SACLs** — target only |

## Diagnostic Procedure
1. Read effective policy (the ground truth, above GPO intent):
```cmd
auditpol /get /category:*
```
2. Standardize on **Advanced Audit Policy** (subcategories) and enable *Force
   audit policy subcategory settings* — mixing legacy "basic" audit with
   advanced causes the 4719 flapping documented in V2.C10.E4719.
3. Size the Security log for the volume you enabled (a 20 MB Security log with
   4688 on wraps in hours; forward off-box or size to days):
```powershell
wevtutil sl Security /ms:1073741824   # 1 GB, or forward via WEF instead
```
4. Volume control for process creation: enable centrally, retain via WEF/SIEM,
   and don't rely on local logs to survive an incident.

## Related Entries
- V2.C9–C11 — the events this enables · V2.C10.E4719 — the flapping trap

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — advanced security audit policy — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — shortlist and volume notes — License: n/a

---
entry_id: V6.C1.E003
title: "Credential Protection: LSA Protection, Credential Guard, LAPS"
category: concept
severity_for_triage: informational
applies_to: ["Windows 10/11 Enterprise; Server 2016+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Three complementary controls target credential theft — the reason the Logon
Type table in V2.C9.E4624 has a "credential exposure" column. **LSA
Protection** (RunAsPPL) makes LSASS a protected process so its memory can't be
read; **Credential Guard** uses virtualization-based security to isolate
secrets from the OS entirely; **Windows LAPS** rotates and escrows local admin
passwords so a stolen local hash is worthless fleet-wide.

## Meaning — and the tickets each generates
- **LSA Protection**: blocks legit software that injects into LSASS (some
  SSO agents, smartcard middleware, older AV) — those break and log
  provider-load failures; audit-mode (event 3065/3066 in
  `Microsoft-Windows-CodeIntegrity/Operational`) previews what would break
  before enforcing.
- **Credential Guard**: incompatible with older auth (unconstrained
  delegation, NTLMv1, some VPN/wireless auth using saved creds), and needs
  VBS/hardware — enabling it fleet-wide without testing breaks specific
  legacy flows. Confirm running state via `msinfo32` ("Virtualization-based
  security Services Running: Credential Guard") or the LSA/DeviceGuard registry.
- **Windows LAPS** (in-box since 2023, superseding legacy LAPS): rotates the
  managed local account; troubleshooting centers on the
  `Microsoft-Windows-LAPS/Operational` channel (policy processing, rotation
  success/failure) and whether the directory (Entra ID or AD) is receiving
  the escrowed password.

## Diagnostic Procedure
```powershell
# LSA protection state
Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name RunAsPPL -EA SilentlyContinue
# Credential Guard / VBS running state
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard |
  Select-Object SecurityServicesConfigured, SecurityServicesRunning
# Windows LAPS
Get-WinEvent -LogName 'Microsoft-Windows-LAPS/Operational' -MaxEvents 20 -EA SilentlyContinue |
  Select-Object TimeCreated, Id, Message
```

## Related Entries
- V2.C9.E4624 — credential-exposure logon types · V6.C1.E001 — baselines enable these

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Credential Guard / LSA protection / Windows LAPS — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — compatibility-ticket notes — License: n/a

---
entry_id: V6.C1.E004
title: "BitLocker: Deployment, Recovery, and Event IDs"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11, Server with BitLocker feature"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
BitLocker's day-to-day troubleshooting is dominated by one scenario:
**unexpected recovery-key prompts**. Understanding *why* the TPM releases or
withholds the key — and where recovery keys are escrowed — is the whole game.
Events live in `Microsoft-Windows-BitLocker/BitLocker Management` and
`-BitLocker Operational`, and TPM events in `Microsoft-Windows-TPM-WMI`.

## Meaning
The TPM seals the volume key to a set of **PCR measurements** (firmware, boot
components, boot config). Anything that changes those measurements makes the
TPM refuse to auto-unlock and forces recovery: firmware/BIOS updates, Secure
Boot changes, boot-order edits, hardware changes (dock/GPU affecting boot),
some feature updates touching the boot chain, or a docking/undocking that
alters measured devices. This is BitLocker working *correctly* — the fix is
knowing the trigger and having the recovery key, not "disabling BitLocker."

Recovery-key escrow locations (verify at least one before enforcing
encryption): Entra ID (Azure AD) device, on-prem AD (msFVE attributes),
Microsoft account (consumer), or a printed/exported key. A fleet without
verified escrow is one firmware update away from mass lockout.

## Diagnostic Procedure
1. Volume and protector state:
```powershell
Get-BitLockerVolume | Select-Object MountPoint, VolumeStatus, ProtectionStatus,
  EncryptionPercentage, EncryptionMethod
(Get-BitLockerVolume -MountPoint C).KeyProtector |
  Select-Object KeyProtectorType, KeyProtectorId
```
2. After an unexpected recovery, find the trigger — recent firmware/Secure
   Boot/boot changes; the Operational channel logs the measurement change:
```powershell
Get-WinEvent -LogName 'Microsoft-Windows-BitLocker/BitLocker Management' -MaxEvents 20 -EA SilentlyContinue |
  Select-Object TimeCreated, Id, Message
```
3. Retrieve the recovery key by its ID (shown on the recovery screen) from the
   escrow directory (Entra/AD) — the KeyProtectorId GUID's first 8 chars match
   the on-screen identifier.
4. Suspend protection (keeps encryption, stops prompting) *before* planned
   firmware updates — the professional way to avoid the prompt:
```powershell
Suspend-BitLocker -MountPoint C -RebootCount 1   # auto-resumes after 1 reboot
```

## Impact
Unmanaged recovery prompts are a top helpdesk volume driver and a genuine
lockout risk without escrow; the controls (suspend-before-firmware, verified
escrow) are entirely preventable-incident territory.

## Related Entries
- V1.C2.E003 — boot chain (what PCRs measure) · V7.C1.E006 — BitLocker cmdlets

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — BitLocker recovery — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — trigger list, suspend-before-firmware — License: n/a

---
entry_id: V6.C1.E005
title: "AppLocker / WDAC Fundamentals"
category: concept
severity_for_triage: medium
applies_to: ["Windows 10/11 Enterprise; WDAC broader"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Two application-control technologies with different strength and blast radius.
**AppLocker** (rules by path/publisher/hash, per user/group) is easier and
softer; **WDAC** (Windows Defender Application Control / App Control for
Business) enforces at the kernel/code-integrity level, machine-wide, and is
far stronger and far less forgiving. Both fail "silently" from the user's view
— an app just won't run — so their *audit events* are the troubleshooting
surface.

## Meaning — where to look when something won't run
| Tech | Audit/enforcement channel | Key IDs |
|---|---|---|
| AppLocker | `Microsoft-Windows-AppLocker/*` (EXE and DLL, MSI and Script, Packaged app-Deployment/Execution) | 8002 allowed, 8003 audited (would block), 8004 blocked |
| WDAC | `Microsoft-Windows-CodeIntegrity/Operational` | 3076 audit-block, 3077 enforced-block, 3089 signing info |

Always deploy in **audit mode first**: AppLocker 8003 and CodeIntegrity 3076
show exactly what *would* be blocked, letting you build allow-rules before
enforcing. Skipping audit mode is how organizations brick line-of-business
apps on rollout.

## Diagnostic Procedure
```powershell
# What AppLocker blocked (or would block in audit)
Get-WinEvent -LogName 'Microsoft-Windows-AppLocker/EXE and DLL' -MaxEvents 30 -EA SilentlyContinue |
  Where-Object Id -in 8003,8004 | Select-Object TimeCreated, Id, Message
# WDAC blocks
Get-WinEvent -LogName 'Microsoft-Windows-CodeIntegrity/Operational' -MaxEvents 30 -EA SilentlyContinue |
  Where-Object Id -in 3076,3077 | Select-Object TimeCreated, Id, Message
```
The blocked file's path, hash, and publisher are in the event — everything
needed to write a precise allow-rule.

## Related Entries
- V6.C1.E003 — LSA protection uses the same CodeIntegrity channel · V2.C11.E4688 — process creation

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — AppLocker / WDAC — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — audit-mode-first, event mapping — License: n/a

---
entry_id: V6.C1.E006
title: "Attack Surface Reduction Rules and Their Event IDs"
category: reference
severity_for_triage: medium
applies_to: ["Windows 10/11 with Defender AV"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
ASR rules are Defender-enforced behavioral blocks (Office spawning children,
credential theft from LSASS, script-launched executables, USB execution, etc.)
identified by GUID. Like application control, they can silently block
legitimate workflows — the events in `Microsoft-Windows-Windows Defender/
Operational` are the reconciliation surface.

## Message Text & Fields
| Event ID | Meaning |
|---|---|
| 1121 | ASR rule **blocked** an operation (enforce mode) |
| 1122 | ASR rule would have blocked (**audit** mode) |
| 5007 | ASR configuration changed (which rules, which mode) |

The event carries the **rule GUID**, the process, and the target — enough to
identify which rule and whether to exclude a path or flip the rule to audit.

## Diagnostic Procedure
1. Current rule states (Enabled=1, Audit=2, Warn=6, Disabled=0):
```powershell
$p = Get-MpPreference
for ($i=0; $i -lt $p.AttackSurfaceReductionRules_Ids.Count; $i++) {
  [pscustomobject]@{ Rule=$p.AttackSurfaceReductionRules_Ids[$i]
                     Action=$p.AttackSurfaceReductionRules_Actions[$i] }
}
```
2. What's being blocked/audited:
```powershell
Get-WinEvent -LogName 'Microsoft-Windows-Windows Defender/Operational' -MaxEvents 40 -EA SilentlyContinue |
  Where-Object Id -in 1121,1122 | Select-Object TimeCreated, Id, Message
```
3. Deploy in **audit (2)** first, read 1122 for two weeks, add per-rule
   exclusions for legitimate hits, then enforce (1). Same discipline as WDAC.

## Related Entries
- V2.C12.E002 — Defender Operational channel · V6.C2.E001 — Defender config

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — ASR rules reference — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — audit-first rollout — License: n/a
