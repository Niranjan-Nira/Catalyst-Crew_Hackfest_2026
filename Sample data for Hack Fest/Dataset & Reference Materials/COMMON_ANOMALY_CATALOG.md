# Common Anomaly Catalog — Beyond These 5 Devices

The 5 sample devices don't contain every kind of problem a new laptop's logs
might show. This catalog lists **other well-known Windows/hardware anomaly
patterns** so your model (or your manual review process) doesn't only
recognize the specific issues that happened to appear in the training set.

**Confidence labeling in this document:** each entry is marked
**[Verified pattern]** (the general behavior is extremely well-documented
and stable across Windows versions) or **[Directionally correct, verify
exact ID]** (the pattern and file/field to check are right, but you should
confirm the precise Event ID against Microsoft Learn or eventid.net before
hard-coding it, since exact IDs can vary by Windows version/subsystem). This
catalog does not invent specifics it isn't confident about.

---

## Disk / Storage (beyond what's in the sample data)

| Pattern | Where to look | Confidence |
|---|---|---|
| **NTFS volume corruption** — Windows detects file system corruption and flags the volume for `chkdsk` on next boot | System event log, source `Ntfs` or `Wininit` (chkdsk autochk results) | [Directionally correct, verify exact ID] |
| **Storage controller timeout** — the disk controller itself (not just one IO) stops responding | System event log, source `stornvme`/`storahci`, "Storport" | [Directionally correct, verify exact ID] |
| **Volume Shadow Copy / backup failures** — recurring failures suggest disk or file-lock issues | Application log, source `VSS` | [Directionally correct, verify exact ID] |

## Memory (beyond what's in the sample data)

| Pattern | Where to look | Confidence |
|---|---|---|
| **Blue-screen bug checks caused by memory** — specific stop codes are well-known memory-related crashes (`0x1A` = memory management, `0x3B` = system service exception, `0x50` = page fault in nonpaged area) | Minidump inventory / kernel crash dumps; the stop code is in the dump filename or `BugCheckCode` in WER `Kernel_*` reports | [Verified pattern] — these specific stop-code *meanings* are long-standing, well-documented Windows internals |
| **Gradual memory leak** — a specific process's working set grows steadily over hours/days without ever releasing memory, eventually exhausting available RAM | A longer-duration resource timeline (this sample only captured 30 min); track one process's memory column over time and check for a monotonic upward trend | [Verified pattern] — the detection method (monotonic growth) is standard; you need a longer capture than what's in this sample data to see it |

## CPU / Thermal (beyond what's in the sample data)

| Pattern | Where to look | Confidence |
|---|---|---|
| **Single-core lockup** — one logical core pinned near 100% while others idle, often a driver or runaway thread | Per-core CPU utilization (not just the `_Total` counter used in this sample's timeline) | [Verified pattern] as a concept; the sample data only captured the aggregate `_Total` counter, not per-core, so you'd need to add that counter to detect this |
| **Fan failure / thermal shutdown** — CPU temperature spikes with no corresponding fan RPM increase (only Device 2's schema captures fan RPM at all) | `Timeline_Thermal_Power_Fan/ThermalPowerFan.csv` — compare `CPU_Temp_C` trend against `Fan_RPM` trend | [Verified pattern] as a concept; only useful if your collector captures fan RPM, which most don't |

## GPU / Display

| Pattern | Where to look | Confidence |
|---|---|---|
| **Display driver Timeout Detection and Recovery (TDR)** — "Display driver stopped responding and has recovered," a well-known GPU driver crash/recovery event | System/Application event log, source `Display` or `nvlddmkm`/`igfx`-style provider names | [Directionally correct, verify exact ID — commonly cited as Event ID 4101 for this scenario, but confirm for your specific Windows build] |
| **Black screen / GPU hang without recovery** — similar to TDR but the system doesn't recover, often requiring a hard reset (would also show as Kernel-Power 41) | Cross-reference a Kernel-Power 41 event with a preceding display-driver event in the same time window | [Verified pattern] as a cross-referencing technique |

## Network

| Pattern | Where to look | Confidence |
|---|---|---|
| **Adapter reset/disconnect loops** — a WiFi or Ethernet adapter repeatedly disconnecting and reconnecting in a short window | `12_Network/WLAN_Report.html` (has disconnect/roam history) or adapter status changes in the System log | [Verified pattern] as a concept; exact event source varies by adapter vendor |
| **DNS resolution failures** — repeated failures to resolve hostnames, often mistaken for "the internet is down" when it's actually just DNS | DNS client operational log, or repeated failures in app-specific logs (browser, VPN client) | [Directionally correct, verify exact ID] |
| **VPN disconnect loops** — a VPN client repeatedly dropping and reconnecting | The specific VPN vendor's own log folder (see `13_AppLogs/`) — format is vendor-specific | [Verified pattern] as a concept; format depends entirely on vendor |

## Battery / Power

| Pattern | Where to look | Confidence |
|---|---|---|
| **Excessive battery wear** — `FullChargeCapacity` has dropped well below `DesignCapacity` (commonly cited as a real problem below ~80% of design) | `10_Battery/BatteryReport.html` (`powercfg /batteryreport` output) — this sample's automated pipeline did not parse this HTML file, so it's a genuine gap in the current dataset | [Verified pattern] as a concept and threshold convention; not automatically extracted in this dataset yet |
| **Rapid unexplained drain** — battery percentage dropping much faster than historical baseline with no corresponding high CPU/GPU usage | Compare `TopConsumers_Timeline.csv`/resource timeline against `Battery_Percent` over the same window | [Verified pattern] as a cross-referencing technique |

## Boot / Startup

| Pattern | Where to look | Confidence |
|---|---|---|
| **Boot time regression** — successive boots take measurably longer than a rolling baseline | Windows Diagnostics-Performance operational log records boot duration per boot | [Directionally correct, verify exact provider/ID for your Windows build] |
| **Classic unexpected-shutdown signature (older/equivalent to Kernel-Power 41)** — historically cited as Event ID 6008, "The previous system shutdown was unexpected" | System log | [Directionally correct — this ID is widely cited in community documentation; behavior can differ by Windows version, so verify] |

## Services / Security

| Pattern | Where to look | Confidence |
|---|---|---|
| **A critical service crashing repeatedly** (not just an app) — e.g. the Print Spooler or Windows Update service terminating unexpectedly | System log, Source "Service Control Manager" — commonly cited Event IDs 7031/7034 for this scenario | [Directionally correct, verify exact ID for your build] |
| **Antivirus/Defender real-time protection unexpectedly disabled** — a common, high-impact security-relevant anomaly | Windows Defender operational log | [Directionally correct, verify exact ID] |
| **Repeated failed update installs with the SAME error code** — a real example already exists in Device 2's own data: `"Installation Failure: Windows failed to install ... with error 0x80073D02"` (this specific error code showed up in the real logs; if it recurs across multiple attempts, that's the pattern to flag) | `WindowsUpdates/InstalledUpdateHistory.csv` or `ReliabilityHistory/ReliabilityRecords.csv` | [Verified pattern] — this exact error appeared in the real sample data once; a genuine anomaly would be this SAME code repeating |

## Application-specific (beyond what's in the sample data)

| Pattern | Where to look | Confidence |
|---|---|---|
| **Browser crash tied to a specific extension** — recurring crashes only occur when a particular extension is enabled | Browser's own crash log folder (`13_AppLogs/GoogleChrome` or `MicrosoftEdge`) cross-referenced with extension install/update timing | [Verified pattern] as a concept; requires browser-specific log parsing not done in this sample's automated pass |
| **Printer driver crash loop** — a print spooler crash tied to a specific driver, recurring every time a print job is sent | Application log + `PrintService` operational log | [Directionally correct, verify exact provider] |
| **Office repeated "repair" cycles** — Office silently re-repairing itself on every launch, a symptom of ongoing corruption rather than a one-time event | Application log, Office Click-to-Run service log; the sample data's `OFFICE_MODULE_VERSION_MISMATCH` finding is a related but distinct pattern (version drift, not repair loops) | [Verified pattern] as a concept, distinct from the confirmed pattern already in this dataset |

---

## How to use this catalog

This is **not** a labeled training set — none of these patterns are backed
by real rows from the 5 sample devices (aside from the update error-code
example, which did occur once). Use it as a checklist when:

1. **A new device's logs come in** and something doesn't match any of the 9
   categories already in `labeled_events_dataset.csv` — check this catalog
   for a plausible match before assuming your pipeline missed something.
2. **You're deciding what additional log sources to collect** — several
   entries above note "not automatically extracted in this dataset yet"
   (per-core CPU, battery HTML report, browser-specific logs) — these are
   natural next additions to the collector if you want broader coverage.
3. **You want to argue your model should generalize**, not just memorize
   the 5 training devices — being able to explain how you'd detect a
   pattern that ISN'T in your training data is a strong signal of real
   understanding, not overfitting.
