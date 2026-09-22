# Volume V · Chapter 1 — Imaging and Provisioning

How Windows gets onto machines, and how that process fails. The through-line:
deployment failures are located by *phase* — WinPE, offline servicing,
specialize/OOBE, or enrollment — each with its own log and its own vocabulary.

---
entry_id: V5.C1.E001
title: "Windows ADK, WinPE, and Answer Files"
category: concept
severity_for_triage: informational
applies_to: ["Windows 10/11 deployment"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The classic deployment toolchain: the **Windows ADK** (Assessment and
Deployment Kit) provides the tools; **WinPE** (a minimal Windows that runs from
RAM) is the environment images are applied from; **answer files**
(`unattend.xml`) automate Setup's questions across its configuration passes.
Even in an Autopilot world, these underlie custom imaging, break-fix media,
and OSD.

## Meaning — the configuration passes (where unattend settings apply)
| Pass | When | Common settings |
|---|---|---|
| windowsPE | In WinPE, before apply | Disk partitioning, image selection, product key |
| offlineServicing | Image mounted, offline | Drivers, packages injected |
| specialize | Hardware detection | Computer name, domain join, OEM info |
| oobeSystem | First boot / OOBE | Local accounts, autologon, first-logon commands |

Answer-file failures are *pass-specific*: a setting in the wrong pass silently
does nothing (the #1 unattend mistake); Setup logs which pass failed. WinPE
itself fails visibly (no boot, missing NIC/storage driver in PE — inject with
DISM).

## Diagnostic Procedure
1. Setup's own logs are the ground truth (locations shift by phase):
   `X:\windows\panther` (WinPE phase), `C:\Windows\Panther\` (later),
   `C:\Windows\Panther\UnattendGC\` (specialize), `setupact.log`/`setuperr.log`.
2. Validate an answer file before deploying (Windows System Image Manager
   validates schema and pass placement).
3. WinPE driver injection when PE can't see disk/network:
```cmd
Dism /Image:C:\WinPE_mount /Add-Driver /Driver:C:\Drivers /Recurse
```

## Related Entries
- V5.C1.E002 — DISM image servicing · V4.C2.E005 — SetupDiag (shares Panther logs)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — ADK / WinPE / unattend — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — pass-placement failure note — License: n/a

---
entry_id: V5.C1.E002
title: "DISM Image Servicing Workflows"
category: procedure
severity_for_triage: informational
applies_to: ["Windows 8+ deployment"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
DISM services *offline* images (a mounted `.wim`/`.vhdx`) the same way it
repairs online ones (V4.C2.E003): add drivers, packages, updates, and features
to the image before deployment so every machine starts patched and equipped.
The mount/commit lifecycle is where this goes wrong.

## Diagnostic Procedure
1. Inspect an image's contents:
```cmd
Dism /Get-ImageInfo /ImageFile:C:\images\install.wim
```
2. Mount → modify → commit:
```cmd
Dism /Mount-Image /ImageFile:C:\images\install.wim /Index:1 /MountDir:C:\mount
Dism /Image:C:\mount /Add-Driver /Driver:C:\Drivers /Recurse
Dism /Image:C:\mount /Add-Package /PackagePath:C:\updates\lcu.msu
Dism /Unmount-Image /MountDir:C:\mount /Commit
```
3. **Recovery from a broken mount** (the classic stuck state — abandoned
   mounts after a crash block future operations):
```cmd
Dism /Get-MountedImageInfo
Dism /Cleanup-Mountpoints
```
4. Servicing logs: `C:\Windows\Logs\DISM\dism.log` — read the tail on any
   failure; build-mismatch (wrong LCU for the image version) is the top
   `Add-Package` failure.

## Related Entries
- V4.C2.E003 — the online counterpart · V5.C1.E001 — WinPE injection

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — DISM image management — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — mount-recovery note — License: n/a

---
entry_id: V5.C1.E003
title: "Windows Autopilot: Profiles, Enrollment, and Failure Codes"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11 with Entra ID + Intune"]
sources:
  - repo: "MicrosoftDocs/memdocs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Autopilot provisions new devices into a managed state with minimal touch: the
device's hardware hash registers it to a tenant, a profile assigns the OOBE
experience, and the **Enrollment Status Page (ESP)** gates the desktop until
policies/apps arrive. Failures cluster at three points: registration, network/
identity during OOBE, and the ESP.

## Meaning — the failure map
| Phase | Common failure | Cause |
|---|---|---|
| Registration | Device not recognized as Autopilot | Hardware hash not uploaded / wrong tenant / profile not assigned |
| OOBE identity | Can't reach Entra/Intune | Network, proxy, time skew, or required endpoints blocked |
| Profile | Wrong/no OOBE experience | Profile assignment timing, group membership |
| ESP | Stuck / timeout / error | A required app or policy failing to install — the ESP surfaces the blocking item |
| Domain join (Hybrid) | Fails to join on-prem AD | Connector, line-of-sight to a DC, OU config — hybrid is the fragile variant |

## Diagnostic Procedure
1. The single best diagnostic — the MDM diagnostics report (captures Autopilot,
   ESP, and policy state):
```cmd
MdmDiagnosticsTool.exe -area Autopilot;DeviceEnrollment;DeviceProvisioning -zip C:\Diag\mdm.zip
```
   Or from Settings → Accounts → Access work or school → Export/collect logs.
2. Live event view during provisioning:
   `Microsoft-Windows-ModernDeployment-Diagnostics-Provider/*` and
   `Microsoft-Windows-DeviceManagement-Enterprise-Diagnostics-Provider/Admin`.
3. Registration/assignment problems are solved in the tenant (Intune portal),
   not on the device — confirm hash upload, profile assignment, and group
   membership there first.
4. ESP hangs: read which app/policy is pending; a single failing required app
   blocks the whole page — that app's install is the real ticket.

## Impact
Autopilot failures block device delivery entirely; the MDM diagnostics zip is
the artifact to attach to every escalation.

## Related Entries
- V5.C2.E001 — MDM enrollment · V5.C2.E003 — hybrid join / dsregcmd

## References & Attribution
- MicrosoftDocs/memdocs — Autopilot troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — failure map — License: n/a

---
entry_id: V5.C1.E004
title: "Provisioning Packages (PPKG)"
category: concept
severity_for_triage: low
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A provisioning package (`.ppkg`, built in Windows Configuration Designer)
applies a bundle of settings — enrollment, Wi-Fi, certificates, apps, policies
— to an existing or OOBE machine without reimaging. The lightweight
alternative to imaging for tweaks and bulk enrollment; useful in break-fix and
kiosk scenarios.

## Diagnostic Procedure
1. Applied-package inventory and results:
```powershell
Get-ProvisioningPackage -AllInstalledPackages |
  Select-Object PackageId, PackageName, IsApplied
```
2. Apply/remove:
```powershell
Install-ProvisioningPackage C:\pkg\config.ppkg
Remove-ProvisioningPackage -PackageId <guid>
```
3. Failures log to `Microsoft-Windows-Provisioning-Diagnostics-Provider/*`;
   the common causes are unmet prerequisites (a setting requiring a version/
   edition the target lacks) and expired embedded certificates.

## Related Entries
- V5.C2.E001 — enrollment (a frequent PPKG payload)

## References & Attribution
- original synthesis — License: n/a
