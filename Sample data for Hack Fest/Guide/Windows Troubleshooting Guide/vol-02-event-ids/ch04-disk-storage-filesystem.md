# Volume II · Chapter 4 — System Log: Disk, Storage, and File System

Reading order for storage triage: hardware-adjacent events first (`disk 7/11/153`,
`storahci/stornvme 129`), then file-system verdicts (`NTFS 55/98`), then paging
consequences (`disk 51`, exception `0xC0000006`). A single failing SSD typically
emits several of these in a recognizable sequence.

---
entry_id: V2.C4.E007
title: "Disk 7: Bad Block"
category: event-id
event: { id: 7, provider: "disk", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `7` — "The device, \Device\Harddisk<N>\DR<M>, has a bad block" — is the
classic disk driver record of an I/O that failed because the medium could not
be read or written at that location. Unlike most storage warnings, this one is
close to unambiguous: the device reported an unrecoverable sector.

## Historical / Technical Context
Emitted by the class driver (`disk.sys`) when a request completes with a
device-reported media error after the port driver's retries are exhausted.
The `Harddisk<N>` index is the disk number as shown in Disk Management;
`DR<M>` is an internal device-object counter that increments across
removals/arrivals, so DR numbers can exceed disk numbers on machines with
removable media history.

## Message Text & Fields
| Field | Meaning | Example |
|---|---|---|
| Device path | `\Device\HarddiskN\DRM` — N = disk number | `\Device\Harddisk1\DR3` |
| Binary data | SRB/sense data — sense key 3 (Medium Error) typical | viewable in Details → hex |

## Meaning
The drive itself said "this sector is unreadable." One-off occurrences on a
drive that then remaps the sector may never repeat; recurring events, or
events clustered across growing LBA ranges, indicate progressive media failure.

## Likely Root Causes
1. **Failing HDD/SSD media** — grown defects; confirming evidence: rising SMART
   reallocated/pending sector counts, more 7s over time. *very common*
2. **Transient write interruption damage** — sectors torn by power loss, later
   unreadable; often follows 41/6008 history. *common*
3. **Cable/enclosure faults mimicking media errors** (mostly external/USB
   drives). *uncommon*

## Diagnostic Procedure
1. Identify the physical disk and check its health counters:
```powershell
Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, HealthStatus, OperationalStatus
Get-PhysicalDisk | Get-StorageReliabilityCounter |
  Select-Object DeviceId, ReadErrorsUncorrected, Wear, Temperature, PowerOnHours
```
2. Trend the events — frequency is the diagnosis:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='disk'; Id=7} |
  Group-Object { $_.TimeCreated.Date } | Select-Object Name, Count
```
3. Map `HarddiskN` to volumes to know what data is at risk:
```powershell
Get-Partition -DiskNumber 1 | Select-Object DriveLetter, Size, Type
```
4. **[MODIFIES SYSTEM]** Back up first, then let the volume remap/verify:
```cmd
chkdsk X: /scan
```

## Resolution
Recurring bad blocks on an internal drive: back up immediately and replace the
drive — remapping buys time, not health. Single historical event with clean
SMART: monitor. External drives: swap cable/enclosure before condemning media.

## Impact
Directly threatens data integrity; bad blocks under the paging file or hives
escalate to crashes (`disk 51`, `0xC0000006`, registry corruption).

## Related Entries
- V2.C4.E051 — Disk 51 paging error
- V2.C4.E055 — NTFS 55 corruption
- V2.C2.E041 — Kernel-Power 41 (torn-write history)

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — disk event guidance — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — prevalence and DR-numbering note — License: n/a

---
entry_id: V2.C4.E011
title: "Disk 11: Controller Error"
category: event-id
event: { id: 11, provider: "disk", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `11` — "The driver detected a controller error on \Device\HarddiskN\DRM"
— reports that the *path* to the device failed: the command didn't complete at
the transport/controller level. Where event 7 blames the medium, 11 blames the
plumbing — cable, port, controller, power delivery, or a device that stopped
responding entirely.

## Meaning
Distinguish by companionship: 11 + `storahci/stornvme 129` resets = device
stopped responding (firmware hang, power state bug); 11 on external drives =
cabling/enclosure/USB power first; 11 across *multiple* disks simultaneously =
controller or driver, not the disks.

## Likely Root Causes
1. **SATA/USB cabling or connector faults** — reseat/replace; dominant on
   desktops and externals. *very common*
2. **Drive firmware hang under load or power-state transition** — pairs with
   129 resets; fix via firmware update or disabling aggressive link power
   management. *common*
3. **Storage controller/driver defects** — vendor RAID/AHCI drivers; multiple
   disks affected. *common*
4. **Insufficient power (bus-powered externals, failing PSU rails)**. *common*

## Diagnostic Procedure
1. Establish scope — one disk or many:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='disk'; Id=11} -MaxEvents 50 |
  Group-Object { ($_.Message -match 'Harddisk\d+') ; $Matches[0] } |
  Select-Object Name, Count
```
2. Check for companion reset events (129) and link-power settings.
3. For externals: different cable, different port (rear I/O, not hub), powered
   enclosure.
4. **[MODIFIES SYSTEM]** Test with AHCI Link Power Management set to Active in
   the active power plan (or vendor guidance) to rule out LPM-induced hangs.

## Resolution
Keyed to causes: replace cabling; update drive firmware and storage drivers;
swap controller port; power remediation. If 11s continue against one disk with
clean transport, treat the drive as suspect despite healthy SMART.

## Impact
Repeated controller errors stall I/O for seconds at a time (system-wide freezes)
and can drop volumes mid-write.

## Related Entries
- V2.C4.E129 — storahci/stornvme 129 resets
- V2.C4.E153 — Disk 153 retried I/O

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C4.E051
title: "Disk 51: Paging Error"
category: event-id
event: { id: 51, provider: "disk", channel: System, level: Warning }
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `51` — "An error was detected on device … during a paging operation" —
means an I/O issued through the paging path failed or was retried. "Paging
operation" is broader than the page file: memory-mapped files and all cached
file I/O travel the same path, so 51 fires for any failing read/write of mapped
sections. It is Warning-level but deserves Error-level attention when recurrent.

## Meaning
What it proves: a paging-path I/O to that device had trouble. What it suggests:
depends on companions — with disk 7/11 it's the same storage fault wearing
another hat; alone on a network-backed or removable device it may just record a
surprise disconnect; under memory pressure with a healthy disk it can indicate
an overwhelmed queue rather than a broken one.

## Likely Root Causes
1. **Same underlying media/transport fault as 7/11/153** — check those first.
   *very common*
2. **Surprise removal / sleep of USB or thin-provisioned disks during mapped
   I/O.** *common*
3. **Storage saturated to timeout by workload (VMs, backup jobs) on marginal
   hardware.** *common*
4. **Failing sectors under pagefile.sys specifically** — pairs with
   `0xC0000006` app crashes and bugcheck `0x7A`. *uncommon but severe*

## Diagnostic Procedure
1. Correlate 51 with 7/11/129/153 in the same window (one query):
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=7,11,51,129,153; StartTime=(Get-Date).AddDays(-7)} |
  Sort-Object TimeCreated | Select-Object TimeCreated, Id, ProviderName, Message -First 40
```
2. Identify whether the device hosts the page file:
```powershell
Get-CimInstance Win32_PageFileUsage | Select-Object Name, AllocatedBaseSize, CurrentUsage
```
3. Watch for downstream evidence: `0xC0000006` in WER reports (V3.C1.E006),
   bugcheck `0x77`/`0x7A` (KERNEL_STACK/DATA_INPAGE_ERROR).

## Resolution
Resolve the underlying 7/11 cause; move the page file off a suspect disk as an
interim mitigation; for removable-device noise, exclude those devices from
mapped-file workloads or disable their selective suspend.

## Impact
Failed paging I/O corrupts the illusion of reliable memory: applications crash
with in-page errors, and in the worst case the kernel bugchecks.

## Related Entries
- V2.C4.E007 · V2.C4.E011 · V3.C1.E006 (0xC0000006)
- V2.C13.E002 — stop code families (0x7A)

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — event 51 guidance — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — companion-based interpretation — License: n/a

---
entry_id: V2.C4.E153
title: "Disk 153: IO Retried"
category: event-id
event: { id: 153, provider: "disk", channel: System, level: Warning }
severity_for_triage: medium
applies_to: ["Windows 8+/Server 2012+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `153` — "The IO operation at logical block address <LBA> for Disk <N>
was retried" — was added so that *recovered* storage problems leave a trace.
No data was lost (the retry succeeded), but the device needed more than one
attempt. It is the early-warning sibling of 7/11: same failure modes, caught
before they became hard errors.

## Meaning
A handful of 153s over months: background noise on some hardware. A rising
rate, or 153s clustering around the same LBA ranges: media degradation in
progress. 153s across many LBAs during power transitions: link/firmware
behavior, not media.

## Likely Root Causes
1. **Early media degradation** — precursor to disk 7. *common*
2. **Link power management / firmware hiccups** — clusters at idle-exit;
   pairs with 129. *common*
3. **Overloaded storage briefly missing timeouts** (heavy VM/backup I/O).
   *common*

## Diagnostic Procedure
1. Rate and LBA clustering:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='disk'; Id=153} -MaxEvents 200 |
  ForEach-Object { if ($_.Message -match 'address (0x[0-9a-fA-F]+).*Disk (\d+)') {
    [pscustomobject]@{ Time=$_.TimeCreated; Disk=$Matches[2]; LBA=$Matches[1] } } } |
  Group-Object Disk | Select-Object Name, Count
```
2. Check SMART trend (`Get-StorageReliabilityCounter`) and correlate with
   idle/wake times for the LPM pattern.

## Resolution
Treat trending 153s on one disk as a pre-failure signal: back up and plan
replacement. LPM-clustered patterns: firmware update or LPM adjustment as in
event 11.

## Impact
Ignored trends convert into events 7/51 and eventually unreadable data — 153
exists precisely to give you the replacement window.

## Related Entries
- V2.C4.E007 · V2.C4.E011 · V2.C4.E129

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C4.E129
title: "storahci/stornvme 129: Reset to Device"
category: event-id
event: { id: 129, provider: "storahci", channel: System, level: Warning }
severity_for_triage: high
applies_to: ["Windows 8+/Server 2012+ (storahci); Windows 10+/Server 2016+ (stornvme)"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `129` from `storahci` (SATA/AHCI) or `stornvme` (NVMe) — "Reset to
device, \Device\RaidPortN, was issued" — records the port driver's recovery
hammer: outstanding commands timed out, so the driver reset the device to
regain control. Each 129 corresponds to a user-visible multi-second I/O freeze.
Note the provider-scoped ID collision: Time-Service also emits an unrelated
`129` — always filter by provider.

## Meaning
The device (or its link) went silent past the timeout (default ~30 s command
window with earlier internal thresholds). The reset usually works, the system
resumes, and the log keeps the receipt. Recurrent 129s = a device that keeps
hanging.

## Likely Root Causes
1. **SSD firmware hangs**, frequently in low-power states — the classic
   "system freezes for 30 seconds, disk light solid" pattern. *very common*
2. **Aggressive link power management (HIPM/DIPM/DevSleep) incompatibilities.**
   *very common*
3. **Failing drive electronics** — resets escalate to 11/7 over time. *common*
4. **Vendor storage-driver defects** (replacing storahci with OEM RAID
   drivers). *uncommon*

## Diagnostic Procedure
1. Confirm provider and frequency:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='storahci','stornvme'; Id=129} -MaxEvents 50 |
  Select-Object TimeCreated, ProviderName, Message
```
2. Match freeze reports/timestamps with the events; check whether they follow
   idle periods (LPM signature) or load (thermal/firmware).
3. Inventory firmware level:
```powershell
Get-PhysicalDisk | Select-Object FriendlyName, FirmwareVersion, MediaType, BusType
```
4. **[MODIFIES SYSTEM]** Apply vendor SSD firmware; if LPM-signature, set AHCI
   Link Power Management to Active in the power plan and re-test.

## Resolution
Firmware update is the durable fix for cause 1; power-plan LPM adjustment for
cause 2; replacement when resets trend upward with SMART degradation.

## Impact
Beyond freezes, timed-out writes during resets are a corruption risk for
databases and VHDs; fleet clusters after an image change usually indicate a
power-plan or driver regression.

## Related Entries
- V2.C4.E011 — controller errors (escalation path)
- V2.C4.E153 — retried I/O (same LPM signature)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C4.E055
title: "NTFS 55: File System Corruption"
category: event-id
event: { id: 55, provider: "Ntfs", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `55` — "The file system structure on volume <X> has now been repaired." /
older form: "…is corrupt and unusable. Please run the chkdsk utility…" — is
NTFS itself declaring that on-disk metadata was found inconsistent. Since
Windows 8, NTFS self-heals many issues online (spot verification + spot
fixing), so modern 55s often report *completed repairs* rather than demands
for chkdsk.

## Historical / Technical Context
Windows 8 restructured NTFS health handling: a corruption detection sets a
verification flag; the Spot Verifier service (`svsvc`) confirms it's real;
online self-healing fixes what it can; only irreparable-online issues set the
dirty bit for boot-time `chkdsk /f`. Events 55, 130, 131, 98 narrate this
pipeline, and `fsutil` exposes the state.

## Meaning
One 55 after a dirty shutdown, followed by a clean 98: the system did its job.
Recurring 55s on the same volume with healthy hardware: suspect the *cause* of
repeated metadata damage — torn writes (power), failing cache/RAM, filter
drivers, or a bug — not just the symptom.

## Likely Root Causes
1. **Unclean shutdown history** — pairs with 41/6008. *very common*
2. **Underlying media/transport faults** — pairs with 7/11/153/129. *very common*
3. **Failing RAM corrupting cached metadata before write-back.** *uncommon*
4. **Third-party filter drivers (AV, backup, dedup) mishandling metadata.**
   *uncommon*

## Diagnostic Procedure
1. Read volume health state without touching anything:
```cmd
fsutil dirty query C:
fsutil repair state C:
```
2. Review the repair narrative — 55/130/131/98 sequence:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Ntfs','Microsoft-Windows-Ntfs'; Id=55,98,130,131} -MaxEvents 40 |
  Sort-Object TimeCreated | Select-Object TimeCreated, Id, Message
```
3. Check the hardware layer per this chapter's earlier entries before blaming
   NTFS.
4. **[MODIFIES SYSTEM]** Force full verification when self-heal keeps
   recurring:
```cmd
chkdsk C: /scan
chkdsk C: /f    & REM offline at next boot for the system volume
```

## Resolution
Fix the upstream cause (power, storage, RAM, filter driver); use `/scan` for
online verification and `/f` for offline repair; if corruption recurs with
clean hardware, memory-test the machine (`mdsched.exe` or memtest86) — RAM is
the classically missed culprit.

## Impact
Metadata corruption can orphan or cross-link files; on system volumes it
escalates to boot failure. Repeated silent self-heals also mask a dying disk
if nobody reads the log.

## Related Entries
- V2.C4.E098 — NTFS 98 volume health summary
- V2.C2.E041 / V2.C2.E6008 — unclean shutdown history

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — NTFS health & chkdsk docs — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — recurrence heuristics — License: n/a

---
entry_id: V2.C4.E098
title: "NTFS 98: Volume Health / chkdsk Results"
category: event-id
event: { id: 98, provider: "Microsoft-Windows-Ntfs", channel: System, level: Information }
severity_for_triage: informational
applies_to: ["Windows 8+/Server 2012+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event `98` — "Volume <X> (\Device\HarddiskVolumeN) is healthy. No action is
needed." — is NTFS's periodic and post-repair clean bill of health. Its value
is as a *timeline anchor*: a 55→98 pair brackets a corruption incident;
absence of a 98 after 55/130 means the volume never reached verified-healthy.

Boot-time chkdsk results, meanwhile, are logged to the **Application** log by
provider `Microsoft-Windows-Wininit`/`Chkdsk` (event `1001`/`26226`-family) —
that's where the full repair transcript lives when an offline fix ran.

## Diagnostic Procedure
1. Health timeline per volume:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Ntfs'; Id=98,55,130,131} |
  Sort-Object TimeCreated | Select-Object TimeCreated, Id, Message -First 30
```
2. Pull the last offline chkdsk transcript:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Microsoft-Windows-Wininit'} -MaxEvents 5 |
  Select-Object TimeCreated, Message | Format-List
```

## Related Entries
- V2.C4.E055 — NTFS 55

## References & Attribution
- original synthesis — License: n/a
