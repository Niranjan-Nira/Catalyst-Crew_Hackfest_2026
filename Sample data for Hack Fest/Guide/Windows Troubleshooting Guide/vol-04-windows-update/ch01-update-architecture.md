# Volume IV · Chapter 1 — How Windows Update Works

You cannot troubleshoot Windows Update from error codes alone — failures land
in different *stages* of a pipeline (scan → download → stage → install →
commit/reboot), and each stage has its own components, logs, and failure
modes. This chapter builds the mental model; Chapter 2 applies it.

---
entry_id: V4.C1.E001
title: "Update Types: Quality, Feature, Driver, Definition, OOB, Checkpoint Cumulative"
category: concept
severity_for_triage: informational
applies_to: ["Windows 10/11, Server 2016+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
"An update failed" means little until you know which *kind*: each type follows
a different installation path and fails differently.

## Meaning
| Type | What it is | Failure character |
|---|---|---|
| Quality update (LCU — the monthly cumulative) | Cumulative OS fixes, servicing-stack content increasingly combined in | CBS/component-store failures (`0x800F0831`, `0x80073712`); install-phase problems |
| Servicing Stack Update (SSU) | Updates the updater itself; now shipped combined with the LCU | Old missing-SSU failures largely eliminated by combining; ordering issues on very stale machines |
| Feature update | New OS version — an in-place setup, not a patch | Setup/compatibility failures with rollbacks — diagnosed via SetupDiag, not WU logs |
| Checkpoint cumulative | LCUs built as differentials on top of a checkpoint LCU (Windows 11 24H2+) | Requires the checkpoint present; reduces size; failure = missing predecessor |
| Driver update | Vendor drivers via WU | Device-specific regressions; blockable by policy |
| Definition update | Defender intelligence — many times daily | Rarely fails; noisy in histories |
| OOB (out-of-band) | Emergency fixes outside Patch Tuesday | Same as quality mechanics |
| .NET / other product updates | Serviced through the same pipeline | Product-specific (MSI/CBS mix) |

Triage implication: quality-update failures → CBS/component-store workflows
(V4.C2.E003); feature-update failures → SetupDiag and compatibility
(V4.C2.E005). Mixing these two playbooks wastes days.

## Related Entries
- V4.C2.E002 — error atlas · V4.C2.E005 — feature-update rollbacks

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — update types & servicing — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V4.C1.E002
title: "The Update Stack: USO, WU Agent, BITS/DO, Servicing Stack, CBS"
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
Five layers, five failure domains. Knowing which layer owns a failure decides
which log you open and which service you inspect.

## Meaning
| Layer | Components | Owns | Watch |
|---|---|---|---|
| Orchestration | Update Session Orchestrator (`UsoSvc`, UsoClient, MoUsoCoreWorker) | Scheduling scans/installs/reboots, deadlines | `Microsoft-Windows-WindowsUpdateClient/Operational`; USO logs |
| Agent | Windows Update service (`wuauserv`, wuaueng) | Talking to WU/WSUS endpoints, evaluating applicability | WindowsUpdate.log (ETW-decoded), result codes `0x8024xxxx` |
| Transport | Delivery Optimization (`DoSvc`) primarily; BITS for some paths | Downloading payloads, peer sharing | `0x80D0xxxx` codes; DO logs/PerfMon |
| Servicing stack | TrustedInstaller (`TiWorker.exe`, CBS) | Staging & committing packages into the component store | `CBS.log`, `0x800Fxxxx` / `0x80073712` |
| Component store | WinSxS + registry component hive | The ground truth of installed components | DISM health commands |

**Stage → dominant error family (original synthesis):** scan fails =
`0x8024xxxx` (agent/network/policy); download fails = `0x80D0xxxx` (DO) or
`0x8024402x` (connectivity); install fails = `0x800Fxxxx`/`0x80073712`
(CBS/store); post-reboot revert = servicing commit or feature-update rollback.

## Diagnostic Procedure
1. Verify the moving parts are present and healthy:
```powershell
Get-Service wuauserv, UsoSvc, DoSvc, TrustedInstaller, BITS |
  Select-Object Name, Status, StartType
```
2. Locate the failure stage from the client's own event channel:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-WindowsUpdateClient/Operational'} -MaxEvents 30 |
  Select-Object TimeCreated, Id, Message
```
   (IDs here: 25/26 scan, 31 download start, 19 install success, 20 install
   failure with the result code.)

## Related Entries
- V4.C2.E001 — reading the logs · V4.C2.E002 — error atlas

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — update stack — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — stage/error mapping — License: n/a

---
entry_id: V4.C1.E003
title: "Delivery Optimization Deep Dive"
category: concept
severity_for_triage: informational
applies_to: ["Windows 10/11"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Delivery Optimization (DO) is the default download engine for WU content,
Store apps, and more — an HTTP downloader with optional peer-to-peer sharing
(LAN, group, or internet peers per policy DownloadMode). It replaces BITS for
update payloads; BITS remains for some legacy paths.

## Meaning
DownloadMode values that matter in the enterprise: 0 (HTTP only), 1 (LAN
peers), 2 (group via GroupID), 3 (internet peers), 99 (offline). Bandwidth
policies (percentages or absolute, business hours aware) live under DO policy,
not BITS. Proxy nuance: DO downloads run as the DoSvc service — user-context
proxies (WinINET) don't apply; system WinHTTP proxy and transparent proxies
do. Firewall: LAN peering needs 7680/TCP inbound.

## Diagnostic Procedure
1. Current status and efficiency:
```powershell
Get-DeliveryOptimizationStatus | Select-Object FileId, FileSize, BytesFromPeers, BytesFromHttp, Status
Get-DeliveryOptimizationPerfSnap
```
2. Effective policy:
```powershell
Get-DeliveryOptimizationLog -Flush | Select-Object -Last 40   # verbose engine log
(Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization' -ErrorAction SilentlyContinue)
```

## Related Entries
- V4.C2.E002 — 0x80D0xxxx codes

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Delivery Optimization — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V4.C1.E004
title: "Servicing Channels, Deferral, and Update Rings"
category: concept
severity_for_triage: informational
applies_to: ["Windows 10/11 enterprise management"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
"Why hasn't this machine updated?" is as common as "why did the update fail?"
— and it's usually *policy working as configured*: channels (General
Availability vs. LTSC), deferral days for quality/feature updates, pauses,
target-version pinning, and ring assignments (WUfB rings in Intune, WSUS
approvals, Autopatch groups) all gate offering.

## Diagnostic Procedure
1. Read the effective update policy state as the client sees it:
```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\PolicyManager\current\device\Update' -ErrorAction SilentlyContinue
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -ErrorAction SilentlyContinue |
  Select-Object DeferQualityUpdates*, DeferFeatureUpdates*, PauseQualityUpdates*, PauseFeatureUpdates*, TargetReleaseVersion*
```
2. Check for safeguard holds on feature updates (offer withheld due to a known
   issue with detected hardware/software) — visible in WU UI messaging and in
   organizational reporting; do not bypass holds on production fleets.
3. Distinguish "not offered" (policy/hold/ring) from "offered and failed"
   (Chapter 2's territory) before touching any repair procedure.

## Related Entries
- V4.C3.E002 — WUfB/Autopatch (queued)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — servicing channels & WUfB — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
