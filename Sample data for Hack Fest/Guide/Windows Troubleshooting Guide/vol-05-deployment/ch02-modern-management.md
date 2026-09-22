# Volume V · Chapter 2 — Modern Management

MDM/Intune replaces (or coexists with) Group Policy on modern fleets, and its
failures are diagnosed differently — through the enrollment state, the CSP
that carried a setting, and the device's identity. Three entries cover the
diagnostic surface.

---
entry_id: V5.C2.E001
title: "Intune/MDM Enrollment Troubleshooting"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11 with Intune/MDM"]
sources:
  - repo: "MicrosoftDocs/memdocs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Enrollment is the foundation — no enrollment, no policy. The
`DeviceManagement-Enterprise-Diagnostics-Provider` channel and the MDM
diagnostics report are where enrollment and policy-application health live.
The most common failures are identity/licensing (not technical device
problems) and are solved by reading, not guessing.

## Meaning — where enrollment fails
| Symptom | Typical cause |
|---|---|
| Auto-enroll never triggers | GPO/registry for MDM auto-enrollment not applied; device not Entra-joined |
| Enrollment fails with an error code | Licensing (no Intune license on the user), MDM authority, or device-cap limits |
| Enrolled but policies not applying | Sync cadence, assignment/targeting, or a specific CSP failing |
| Falls out of management | Token/cert expiry, device object deleted in Entra |

## Diagnostic Procedure
1. Collect the authoritative report:
```cmd
MdmDiagnosticsTool.exe -area DeviceEnrollment;DeviceProvisioning -zip C:\Diag\mdm.zip
```
2. Read enrollment state and the diagnostics channel:
```powershell
Get-WinEvent -LogName 'Microsoft-Windows-DeviceManagement-Enterprise-Diagnostics-Provider/Admin' -MaxEvents 40 -EA SilentlyContinue |
  Select-Object TimeCreated, Id, Message
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Enrollments' |   # enrollment GUIDs & state
  ForEach-Object { Get-ItemProperty $_.PSPath } |
  Where-Object EnrollmentState | Select-Object ProviderID, EnrollmentState, UPN
```
3. Force a sync and watch results:
```powershell
Get-ScheduledTask -TaskPath '\Microsoft\Windows\EnterpriseMgmt\*' |
  Where-Object TaskName -like '*PushLaunch*' | Start-ScheduledTask
```
   (Or Settings → Access work or school → Info → Sync.)
4. Licensing/assignment problems are tenant-side — confirm in the Intune
   portal (device compliance, assignment, per-user license) before touching
   the device.

## Related Entries
- V5.C2.E002 — CSPs (what enrollment delivers) · V5.C1.E003 — Autopilot uses this

## References & Attribution
- MicrosoftDocs/memdocs — MDM enrollment troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — failure table — License: n/a

---
entry_id: V5.C2.E002
title: "CSPs and the MDM Diagnostic Report"
category: concept
severity_for_triage: medium
applies_to: ["Windows 10/11 with MDM"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A **Configuration Service Provider (CSP)** is the on-device interface that
turns an MDM policy into an actual Windows setting — the MDM equivalent of a
Group Policy client-side extension. When "the Intune policy isn't working," the
question is *which CSP carried it and what did it report* — and the MDM
diagnostic report's HTML answers exactly that.

## Meaning
The report (`MDMDiagReport.html`, produced by the diagnostics tool) lists every
enrolled policy, the CSP/OMA-URI, the value pushed, and the result — including
error HRESULTs per setting. Common CSP failure patterns: a setting unsupported
on the device's edition/version (silently ignored or errored), conflicting
policies (GPO and MDM setting the same thing — MDM/GP coexistence rules
decide), or a value the CSP rejects. Reading the per-setting result turns
"policy not applying" into "this OMA-URI returned 0x8018000X."

## Diagnostic Procedure
1. Generate the human-readable report:
```cmd
MdmDiagnosticsTool.exe -out C:\Diag\MDMReport
```
   → open `MDMDiagReport.html`; find the failing area's CSP and its result code.
2. Registry view of pushed policies (advanced):
   `HKLM\SOFTWARE\Microsoft\PolicyManager\current\device\<Area>` shows the
   effective MDM-set values by area.
3. For GP-vs-MDM conflicts, check whether *MDMWinsOverGP* applies and which
   authority is expected to win for that setting.

## Related Entries
- V5.C3.E001 — the Group Policy analog · V5.C2.E001 — enrollment

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — CSP reference / MDM diagnostics — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — per-setting-result framing — License: n/a

---
entry_id: V5.C2.E003
title: "Hybrid Join and Entra ID Device States (dsregcmd /status)"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11 with Entra ID"]
sources:
  - repo: "MicrosoftDocs/azure-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A device's **identity state** underlies SSO, Conditional Access, Windows Hello,
and MDM enrollment — and `dsregcmd /status` is the one command that reads it
all. The states: Entra-joined (cloud only), Hybrid-joined (on-prem AD + Entra),
Entra-registered (personal device, work access), or domain-joined only.
Hybrid is the most failure-prone because it requires *both* directories to
agree.

## Meaning — reading dsregcmd /status
| Field | Healthy | If not |
|---|---|---|
| `AzureAdJoined` | YES (managed devices) | Registration/sync problem |
| `DomainJoined` | YES (hybrid) | Not on-prem joined |
| `DeviceAuthStatus` | SUCCESS | Device cert/identity broken |
| `TenantName`/`TenantId` | your tenant | Wrong/blank = not registered |
| SSO State `AzureAdPrt` | YES | No Primary Refresh Token → SSO and Conditional Access fail |
| `NgcSet` | YES if Hello configured | Hello for Business not provisioned |
| `KeySignTest` (diagnostics) | PASSED | Device key / TPM problem |

The **PRT (Primary Refresh Token)** is the crux of modern SSO: no PRT (`AzureAdPrt: NO`) means every cloud sign-in prompts and Conditional Access
may block — caused by network to Entra, time skew, or a broken device cert.

## Diagnostic Procedure
1. Full identity state:
```cmd
dsregcmd /status
```
2. Deeper diagnostics (tests device auth and key sign):
```cmd
dsregcmd /status /debug
```
3. Hybrid-join failures: confirm Entra Connect is syncing device objects,
   the device has line-of-sight to a DC, and (for federated setups) the
   Service Connection Point is configured; the on-prem→cloud device sync can
   lag, so a freshly joined device may not appear immediately.
4. PRT problems: check network/proxy to Entra endpoints, time sync
   (V2.C6.E129 — skew breaks token issuance), and re-trigger with a lock/
   unlock or sign-out.

## Impact
Broken device identity cascades into SSO prompts, Conditional Access blocks,
Hello failures, and enrollment loss — `dsregcmd /status` is the first command
for any "can't sign in to cloud apps / keeps prompting" ticket on a managed
device.

## Related Entries
- V5.C2.E001 — enrollment depends on this · V2.C6.E129 — time skew breaks PRT

## References & Attribution
- MicrosoftDocs/azure-docs — device identity / dsregcmd — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — PRT-centric framing — License: n/a
