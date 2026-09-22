# Volume IV · Chapter 2 — Diagnosing Update Failures

Workflow discipline: (1) identify the failing update and its type, (2) get the
result code and map it to a stage, (3) open the *stage's* log, (4) repair the
narrowest thing that fixes it. Component reset is step last, not step one.

---
entry_id: V4.C2.E001
title: "Reading WindowsUpdate.log (Get-WindowsUpdateLog) and CBS.log"
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
Two logs answer most update questions. **WindowsUpdate.log** (agent layer) is
no longer a live text file — it's ETW traces that must be decoded on demand.
**CBS.log** (servicing layer, `C:\Windows\Logs\CBS\CBS.log`) is live text and
is where install-phase `0x800Fxxxx` failures explain themselves.

## Diagnostic Procedure
1. Decode the agent log (writes to Desktop by default):
```powershell
Get-WindowsUpdateLog -LogPath C:\Diag\WindowsUpdate.log
```
2. Read it by *transaction*: find the failing update's title, then follow its
   thread — scan result, download job, install handoff, result code. Search
   for `FAILED` and `, hr=8` patterns near the update's KB number.
3. CBS.log triage — jump to the errors instead of scrolling gigabytes:
```powershell
Select-String -Path C:\Windows\Logs\CBS\CBS.log -Pattern ', Error\s+CBS' |
  Select-Object -Last 30
```
   Around each error, the preceding lines name the package and component being
   processed — that package identity is the actionable fact.
4. Companion files: `CbsPersist_*.cab` (archived CBS logs),
   `C:\Windows\Logs\DISM\dism.log` (repair operations),
   `C:\Windows\SoftwareDistribution\ReportingEvents.log` (agent history in
   plain text — underrated quick read).
5. Correlate with the event channel (`WindowsUpdateClient/Operational` ID 20
   carries the same result code with a timestamp — fastest starting point).

## Related Entries
- V4.C2.E002 — decoding the codes you just found
- V4.C2.E003 — component-store repair

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — update log files — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — reading order — License: n/a

---
entry_id: V4.C2.E002
title: "The 0x8007xxxx / 0x8024xxxx / 0x800Fxxxx / 0x80D0xxxx Error Code Atlas"
category: reference
severity_for_triage: high
applies_to: ["Windows 10/11, Server 2016+"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "Windows SDK (winerror.h) — referenced"
    license: "referenced, not reproduced"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Update result codes are HRESULTs, and the *facility* prefix tells you the
layer before you look anything up: `0x8007xxxx` wraps a plain Win32 error
(last 4 hex digits = the Win32 code); `0x8024xxxx` is the WU agent's own
facility; `0x800Fxxxx` is CBS/servicing; `0x80D0xxxx` is Delivery
Optimization; `0xC1900101` is the feature-update/setup family.

**Decode trick:** for any `0x8007xxxx`, convert the low word to decimal and
read the Win32 error: `0x80070002` → 2 → file not found.
```powershell
# Universal decoder for the embedded code
$hr = 0x80070005; [ComponentModel.Win32Exception]::new($hr -band 0xFFFF).Message
```

## Message Text & Fields — the atlas
**0x8007xxxx (wrapped Win32):**
| Code | Win32 | Meaning in WU context | First move |
|---|---|---|---|
| `0x80070002` | 2 file not found | Missing/corrupt download or store file | Clear SoftwareDistribution (E006); DISM scan |
| `0x80070003` | 3 path not found | Same family as 0002 | Same |
| `0x80070005` | 5 access denied | ACL damage, AV interference on servicing paths | AV exclusions check; SFC/DISM |
| `0x8007000E` | 14 out of memory | Resource exhaustion during scan (old/huge catalogs) | Reboot, retry; check for memory pressure |
| `0x80070020` | 32 sharing violation | File locked by another process (AV/backup) | Identify locker; retry clean-boot |
| `0x8007007E` | 126 module not found | Missing DLL in the update plumbing | SFC; component repair |
| `0x80070422` | 1058 service disabled | wuauserv/UsoSvc disabled by "optimizer" tools or policy | Re-enable services |
| `0x800705B4` | 1460 timeout | Operation timed out (scan against overloaded WSUS is classic) | Server-side health; retry window |
| `0x80070490` | 1168 element not found | Corrupt component/manifest reference | DISM RestoreHealth |

**0x8024xxxx (WU agent):**
| Code | Meaning | First move |
|---|---|---|
| `0x80240034` | Download failed | DO/connectivity path (E003 in Ch1); retry; check proxy |
| `0x8024402C` / `0x80244022` | Proxy/name resolution / HTTP 503 to endpoint | Test endpoint reachability as SYSTEM (WinHTTP proxy!) |
| `0x8024401C` | HTTP timeout to service/WSUS | Server health, network path |
| `0x80244010` | Too many round trips (huge WSUS catalog) | WSUS maintenance: decline superseded, reindex |
| `0x80240022` | All updates failed to download | Transport-wide: proxy/SSL inspection breaking DO |
| `0x8024000B` | Operation cancelled | Policy/user cancellation — usually noise |
| `0x80240017` | Not applicable | Prereq missing or already superseded — often not a real failure |
| `0x8024500C` | Update service shutdown/policy conflict | Conflicting dual-scan/policy configuration |

**0x800Fxxxx (CBS/servicing):**
| Code | Meaning | First move |
|---|---|---|
| `0x800F0831` | Store corruption: missing predecessor package manifest | DISM RestoreHealth with a known-good source; on checkpoint LCUs, ensure the checkpoint installed |
| `0x800F081F` | Repair source not found (DISM) | Provide /Source (matching-build WIM or update media) |
| `0x800F0922` | Install commit failed — classically System Reserved partition full or VPN-blocked servicing | Free the reserved partition; retry off-VPN |
| `0x800F0988` / `0x800F0982` | Component processing/pinning failure in a specific package | Targeted: identify the package in CBS.log; often fixed by later LCU |
| `0x80073712` | ERROR_SXS_COMPONENT_STORE_CORRUPT — the flagship corruption code | The E003 workflow, exactly |

**0x80D0xxxx (Delivery Optimization):**
| Code | Meaning | First move |
|---|---|---|
| `0x80D02002` | DO download timeout | Bandwidth policy too tight; proxy interference |
| `0x80D02013` / `0x80D0200E` | DO job errors (config/peer) | Set DownloadMode 0 as a test — if it fixes it, the problem is peering/policy |

**0xC1900101-xx (feature update rollbacks)** — the second byte after the
dash names the setup phase (`-0x20017` SafeOS/boot, `-0x30018` first boot,
`-0x40017` second boot): driver and firmware territory → SetupDiag (E005).

## Related Entries
- V4.C2.E003 — corruption repair · V4.C2.E005 — SetupDiag
- V3.C1.E005 — WindowsUpdateFailure3 WER reports carry these same codes

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — Windows Update error reference — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- Windows SDK winerror.h — code names referenced — not reproduced
- original synthesis — facility-first triage, first-move column — License: n/a

---
entry_id: V4.C2.E003
title: "Component Store Corruption: DISM RestoreHealth Workflows"
category: procedure
severity_for_triage: high
applies_to: ["Windows 8+/Server 2012+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The component store (WinSxS + its registry hive) is the ground truth CBS
installs from; when its manifests/payloads corrupt, updates fail with
`0x80073712`/`0x800F0831` and SFC can't repair system files. DISM's health
commands check and rebuild the store; SFC then repairs the *live* files from
the healed store. Order matters: **DISM first, SFC second.**

## Diagnostic Procedure
1. Read-only pass — is the store marked or actually corrupt:
```cmd
DISM /Online /Cleanup-Image /CheckHealth
DISM /Online /Cleanup-Image /ScanHealth
```
2. **[MODIFIES SYSTEM]** Repair from Windows Update (or WSUS if policy points
   there):
```cmd
DISM /Online /Cleanup-Image /RestoreHealth
```
3. If RestoreHealth fails with `0x800F081F`/`0x800F0906` (source not found) —
   typical on WSUS-managed or disconnected machines — supply a source of the
   **same build**: mount the matching ISO/ESD and:
```cmd
DISM /Online /Cleanup-Image /RestoreHealth /Source:ESD:D:\sources\install.esd:1 /LimitAccess
```
   (`/LimitAccess` stops it falling back to WSUS; index 1 = check with
   `DISM /Get-WimInfo`.) Build mismatch between source and OS is the #1 reason
   this step "doesn't work."
4. Then repair live files:
```cmd
sfc /scannow
```
5. Verify by reviewing the tail of `dism.log` and re-attempting the failed
   update; confirm the failing package from CBS.log now processes.
6. Escalation path when corruption persists: install the latest LCU manually
   from the Microsoft Update Catalog (later cumulative often replaces the
   broken component outright); final resort is an in-place upgrade repair
   (setup.exe from matching media, keep files and apps) — rebuilds the store
   wholesale.

## Impact
An unrepaired store fails every future cumulative — the machine's patch level
freezes, which is a security exposure clock ticking.

## Related Entries
- V4.C2.E002 — the codes this fixes · V1.C3.E007 — DISM/SFC tool entry (queued)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — repair a Windows image — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — escalation ladder — License: n/a

---
entry_id: V4.C2.E004
title: "Stuck at N%: Install-Phase Failure Patterns"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
"Stuck" usually isn't — CBS processing of a large cumulative legitimately
holds at fixed percentages for long stretches while TiWorker churns. The
diagnostic question is *working or wedged*, answerable in two minutes without
rebooting.

## Diagnostic Procedure
1. Is the servicing worker consuming CPU/disk?
```powershell
Get-Process TiWorker, TrustedInstaller -ErrorAction SilentlyContinue |
  Select-Object Name, CPU, WS
```
2. Is CBS.log still growing?
```powershell
1..2 | ForEach-Object { (Get-Item C:\Windows\Logs\CBS\CBS.log).Length; Start-Sleep 30 }
```
   Growing log + busy TiWorker = let it run (an hour on slow disks is normal).
   Static log + idle worker for 30+ minutes = genuinely wedged.
3. Wedged: capture the last CBS operations (they name the package/component it
   died in), then reboot — CBS is transactional and will roll back or resume;
   never power-cut during "Working on updates" unless truly hung at the
   firmware level.
4. Post-reboot, decode the result (E001/E002) and repair per the code. Repeat
   wedging in the same package = corruption (E003); wedging in driver installs
   = pull the device's driver events (Kernel-PnP 219).

## Related Entries
- V4.C2.E001 · V4.C2.E003

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V4.C2.E005
title: "Rollbacks and SetupDiag for Feature Update Failures"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11 feature updates"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A feature update that fails *reverts* — the machine boots the old build and
reports a `0xC1900101`-style code. The evidence lives in setup's own logs
(`$WINDOWS.~BT\Sources\Panther`, `Rollback` folders), and **SetupDiag** is the
Microsoft tool that reads them all and names the failure rule — run it before
any manual log spelunking. On current builds SetupDiag runs automatically
after a rollback and drops results locally.

## Diagnostic Procedure
1. Check for existing automatic results:
```powershell
Get-ChildItem 'C:\Windows\Logs\SetupDiag' -ErrorAction SilentlyContinue
Get-ItemProperty 'HKLM:\SYSTEM\Setup\SetupDiag\Results' -ErrorAction SilentlyContinue
```
2. Or run it fresh (download from Microsoft; single exe):
```cmd
SetupDiag.exe /Output:C:\Diag\SetupDiagResults.log
```
3. Read the matched rule: it typically names a blocking driver, a plug-in
   failure phase, disk space, or a specific known signature. The
   `0xC1900101-0xNNNNN` extended code's phase (SafeOS/first boot/second boot)
   corroborates: those phases are dominated by storage/display/network driver
   and firmware issues.
4. Standard remediations by finding: update or remove the named driver
   (especially storage and AV filter drivers), firmware update, free disk
   space (10+ GB), disconnect nonessential peripherals, retry.

## Related Entries
- V4.C2.E002 — 0xC1900101 family · V5.C1 — deployment volume (queued)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — SetupDiag — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V4.C2.E006
title: "Reset-WindowsUpdate: Safe Component Reset Procedure"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 10/11, Server 2016+"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The famous "reset Windows Update components" ritual — clearing
SoftwareDistribution and catroot2 — is a legitimate fix for *download/metadata*
corruption (`0x80070002`, endless scan loops, wrong-size downloads). It does
nothing for CBS/store corruption, and cargo-culting it first destroys the
evidence (logs and download state) you needed. Use it deliberately, after the
code says transport/metadata.

## Diagnostic Procedure
**[MODIFIES SYSTEM]** — full sequence:
```cmd
net stop wuauserv
net stop cryptSvc
net stop bits
net stop msiserver
ren C:\Windows\SoftwareDistribution SoftwareDistribution.old
ren C:\Windows\System32\catroot2 catroot2.old
net start msiserver
net start bits
net start cryptSvc
net start wuauserv
```
Then trigger a scan:
```powershell
Start-Process UsoClient.exe -ArgumentList 'StartInteractiveScan'
```
Notes: renaming (not deleting) preserves a rollback and the old
ReportingEvents.log for forensics; update *history display* resets (the
installed state does not — that lives in CBS); catroot2 rebuilds
automatically. Delete the `.old` folders after confirming health.

## Impact
Overuse masks recurring root causes: if a machine needs this monthly, the real
problem is upstream (disk, AV interference, proxy) — investigate, don't ritualize.

## Related Entries
- V4.C2.E002 — when the code justifies this · V4.C2.E003 — the CBS-side counterpart

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — reset WU components — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — when-not-to guidance — License: n/a
