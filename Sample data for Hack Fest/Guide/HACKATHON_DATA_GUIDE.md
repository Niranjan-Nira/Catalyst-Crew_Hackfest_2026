# Hackathon Data Guide — Reading the Raw Diagnostic Logs

This is the raw output of a 17-module Windows diagnostic collector run against a
real enterprise laptop. It is intentionally **not pre-processed** — you are
expected to parse, correlate, and reason over it yourselves. This guide tells
you: how to read each file type, what's inside each folder, how to approach
different anomaly categories, and what output format is expected.

---

## Part 1 — How to read the raw files

You'll encounter three file types in this dataset. Each needs a different
approach.

### 1.1 CSV files (majority of the data)
Read normally with any CSV/DataFrame library (pandas, etc.). Two things to
watch for:
- **An empty CSV is not necessarily "no problem."** It can also mean "nothing
  was found" (good) or "couldn't be collected" (uninformative). Always check
  `_StatusReport\StatusReport.txt`/`.csv` first — it tells you which of the 16
  collection phases succeeded, partially succeeded, or failed, and why
  (commonly: needs Administrator privileges, or a Windows API genuinely
  returned zero matching events).
- Dates appear in **mixed formats** across files (some `dd-MM-yyyy`, some ISO
  `yyyy-MM-ddTHH:mm:ss`) because they come from different underlying Windows
  APIs — normalize before comparing timestamps across files.

### 1.2 Raw `.evtx` files (`02_EventLogs\Raw_EVTX\*.evtx`)
These are Windows' native binary event log format — 166 of them were exported
in this collection. You do not need to parse these directly for most analysis:
**a pre-converted, readable CSV version of each log already exists** in
`02_EventLogs\CSV_Readable\*.csv` (same filename, `.csv` instead of `.evtx`),
capped at the most recent 2000 events per log. Use the CSV version unless you
need an event beyond that cap or want to open one specific log natively in
Event Viewer for full forensic detail (`python-evtx` or `Get-WinEvent` in
PowerShell can also parse `.evtx` directly if needed).

### 1.3 `Report.wer` files (`15_CrashDumps_WER\<crash_folder>\Report.wer`)
These are **UTF-16LE encoded plain text**, not binary — but many tools assume
UTF-8 and will show garbage or fail. Decode with UTF-16LE first (Python:
`open(path, encoding="utf-16-le")`, or the CLI: `iconv -f utf-16le -t utf-8`).

Each file is a flat `Key=Value` list. The fields that matter most:
- `EventTime=<number>` — **this is a Windows FILETIME value, not Unix time.**
  Convert it with: `datetime(1601,1,1) + timedelta(microseconds=EventTime/10)`.
  This is the actual crash timestamp — do not rely on the folder's filesystem
  `LastWriteTime` in `WER_ReportManifest.csv`, which can differ slightly from
  the true `EventTime` inside the report.
- `EventType=` — the WER "bucket," e.g. `APPCRASH`, `AppHang`,
  `OFFICE_MODULE_VERSION_MISMATCH`, `LiveKernelEvent`, `CLR20r3` (.NET crash),
  `BEX64` (buffer/exception fault) — this alone often tells you the *category*
  of failure before you look at anything else.
- `Sig[n].Name` / `Sig[n].Value` pairs — the specific signature of the crash
  (faulting module, version, offset). Two crashes with the same `Sig` values
  are the *same underlying bug* recurring, not two different problems.
- The folder name itself encodes the category prefix: `AppCrash_`, `AppHang_`,
  `Critical_`, `NonCritical_`, `Kernel_<stopcode>_` — filter/group by this
  prefix before you even open the file.

---

## Part 2 — What's in each folder (all 17)

| Folder | Contents | Format notes |
|---|---|---|
| `01_Timeline_And_Resources` | 30-min live capture: CPU/mem/GPU/NPU %, active window title, process start/stop, file create/change/delete events, any crash during the window | CSV, one row per ~5-sec sample |
| `02_EventLogs` | Every Windows event log — raw `.evtx` + readable `.csv` (166 logs in this run) | See 1.2 above |
| `03_WindowsUpdates` | Installed KBs, full update history, pending updates, OS version | CSV |
| `04_HardwareDevices` | Device Manager inventory, driver versions/dates, **`ProblemDevices_ONLY.csv`** (non-OK status), **`DevicesWithConfigManagerErrors.csv`** (numeric error codes) | CSV — see Part 3.3 for how to read error codes |
| `05_Disk` | Drive size/free space, physical disk health, SMART reliability counters, disk-related System log events | CSV |
| `06_Memory` | RAM modules, usage snapshot, **`WHEA_HardwareMemoryErrors.csv`** (hardware-level errors), memory diagnostic results, top memory consumers | CSV |
| `07_CPU` | CPU details, throttling events, WHEA CPU errors, temperature (if sensor accessible) | CSV; temp often `N/A` on enterprise firmware |
| `08_SystemInfo` | Make/model/serial/BIOS, all drivers, OEM software, `systeminfo` raw dump | CSV/TXT |
| `09_ReliabilityMonitor` | **`ReliabilityRecords_Full.csv`** (every failure Windows logged, with technical detail), **`StabilityIndex_DailyScore.csv`** (1–10 daily score, actually recorded ~hourly) | CSV |
| `10_Battery` | `powercfg` battery report (HTML), current status, AC/DC state | HTML + CSV |
| `11_StartupApps` | Startup programs, enabled/disabled state, active scheduled tasks with last run result | CSV/TXT |
| `12_Network` | Adapters, IP config, WiFi interface/report, throughput sample, ping test | CSV/TXT/HTML |
| `13_AppLogs` | Copied log folders from specific installed apps (VPN, Teams, Outlook, etc. — whichever were found on this machine) | Native app log formats, varies |
| `14_InstalledApps` | Installed software (registry, MSI, UWP) with version + install date | CSV |
| `15_CrashDumps_WER` | Windows Error Reporting crash archive — one folder per crash/hang, `WER_ReportManifest.csv` index, minidump inventory | See 1.3 above |
| `16_Services_Processes` | Service/process snapshot, Service Control Manager history, persistent app crash/hang history | CSV |
| `_StatusReport` | Per-phase success/partial/failed status for the collection itself | CSV/JSON/TXT — **read first** |

---

## Part 3 — Approach by category

Different categories of anomaly need different investigative moves. Below is
the playbook per category.

### 3.1 Application anomalies (crashes, hangs, version issues)
**Files:** `15_CrashDumps_WER\*`, `16_Services_Processes\AppCrashHang_PersistentHistory.csv`, `02_EventLogs\CSV_Readable\Application.csv`

1. Group WER folders by `EventType` (APPCRASH vs AppHang vs specific buckets
   like `OFFICE_MODULE_VERSION_MISMATCH`) — different buckets need different
   fixes.
2. Within a bucket, group by faulting process/module `Sig` values. **3+
   occurrences of the identical signature = a real recurring bug, not noise.**
3. Check if the crashed module's *version* changes across occurrences (see the
   PowerPoint example: two different build numbers across three crashes points
   to a partial/interrupted update, not a single bad build).
4. Cross-reference the crash timestamp (decoded `EventTime`) against
   `14_InstalledApps` install dates and `03_WindowsUpdates` KB install dates —
   did the app or a shared component change shortly before crashes started?

### 3.2 System stability / multi-process correlation
**Files:** `15_CrashDumps_WER\*` (all types together), `09_ReliabilityMonitor\*`

1. **Don't filter by application here — look at ALL crash timestamps across
   every process together**, sorted chronologically.
2. Look for **tight clusters**: multiple unrelated processes (different
   vendors, different purposes) crashing within seconds to a couple of minutes
   of each other. Unrelated processes crashing together is not coincidence —
   it means something they all depend on (a shared driver, a security agent
   hooking into all processes, a resource exhaustion event) triggered it.
3. Within a cluster, find the **first process to fail** by timestamp — it's
   often (not always) the trigger, especially if it's a system-level agent
   (security/monitoring software) rather than an ordinary user app.
4. Check `14_InstalledApps` for anything installed in the days before the
   cluster — a newly installed agent that hooks into other processes (EDR,
   endpoint monitoring, DLP tools) is a common root cause for this pattern.
5. Use `StabilityIndex_DailyScore.csv` to confirm the cluster's date shows a
   visible dip, corroborating it wasn't a one-off blip Windows already
   smoothed over.

### 3.3 Driver / hardware anomalies
**Files:** `04_HardwareDevices\*`, `06_Memory\WHEA_HardwareMemoryErrors.csv`, `07_CPU\CPU_WHEA_Errors.csv`, `05_Disk\Disk_ReliabilityCounters_SMART.csv`

1. **`ProblemDevices_ONLY.csv` is noisy — most entries are `CM_PROB_PHANTOM`,
   which just means a USB/peripheral device isn't currently plugged in. This
   is normal, not a fault.** Ignore phantom entries.
2. **`DevicesWithConfigManagerErrors.csv` is the high-signal file** — it only
   lists devices with a genuine non-zero error code. Common codes:
   - `CM_PROB_FAILED_POST_START` — device failed to initialize after starting
     (often a driver crash or firmware issue)
   - Numeric codes like `43` — Windows stopped the device due to a reported
     problem (frequently a driver issue)
3. Any row at all in `WHEA_HardwareMemoryErrors.csv` or `CPU_WHEA_Errors.csv`
   is a hardware-level signal — these are not "usage is high," they are the
   CPU's own error-correction hardware reporting a fault. Treat presence
   alone as significant regardless of count.
4. For a driver suspected of causing device failure, cross-check
   `04_HardwareDevices\DriverDetails_VersionInstallDate.csv` (or
   `08_SystemInfo\AllDrivers_VersionDate.csv`) for that device's driver
   version/install date against when the error started appearing.

### 3.4 Network anomalies
**Files:** `12_Network\*`

1. `WiFi_Interface_Raw.txt` / `WLAN_Report.html` show connection type, signal
   strength, and — critically — the WLAN report includes a disconnect/roam
   history over time, useful for correlating "device X had problems" against
   "WiFi dropped at that exact time."
2. `NetworkThroughput_10sSample.csv` and `PingTest_Latency.csv` are only a
   point-in-time snapshot at collection time — treat these as context, not
   proof of an ongoing pattern, unless corroborated by repeated complaints or
   event log entries.
3. If a network *driver* (not just connectivity) is suspected, cross-check
   with Part 3.3 — a "Net" class error in `DevicesWithConfigManagerErrors.csv`
   is a hardware/driver anomaly that will manifest as network symptoms, so it
   belongs to both categories.
4. Chronic, high-frequency errors from a *display or peripheral* provider
   (not the network itself) can sometimes look network-adjacent if the device
   connects via USB-C dock — check `08_SystemInfo` for dock/hub hardware
   before assuming a pure network fault.

### 3.5 Live/real-time correlation (the 30-minute capture)
**Files:** `01_Timeline_And_Resources\*`

1. This is your only file where you can watch cause-and-effect happen live.
   Line up `ResourceUtilization_Timeline.csv` (CPU/mem/GPU per ~5 sec) against
   `TopProcesses_PerSample.csv` (which process was heaviest at that instant)
   and `ProcessStartStop_Timeline.csv` (did something start or stop right
   there).
2. **A memory or CPU number that's already extreme even while the machine is
   reported "quiet"** (no process/file/crash events that window) is itself a
   flag — it means baseline resource pressure exists even without an active
   trigger, which is a leading indicator for hangs that show up elsewhere
   (Reliability Monitor, WER `AppHang` entries) rather than a live crash you
   happened to catch in this particular 30 minutes.
3. If nothing anomalous shows up in this file, that's expected and fine — 30
   minutes is a small window; absence here doesn't clear the machine, it just
   means you need the historical files (WER, Event Logs, Reliability Monitor)
   to find anything that didn't happen to occur during the capture.

---

## Part 4 — Expected output format

Your final deliverable is a **case report** with four explicit tiers. Do not
collapse these into a single flat list — the tier itself communicates how
sure you are, and judges will check that your tier assignment matches your
stated evidence, not just that you found something.

### Tier 1: Anomalies (high confidence — clear, corroborated evidence)
Something you can state as fact because multiple independent signals agree,
or the evidence is unambiguous on its own (e.g. an exact repeated crash
signature, a hardware error code that only means one thing).

### Tier 2: Possible Anomalies (moderate confidence — worth flagging, needs more data)
A signal that's real and worth reporting, but where you can also state
*why* it isn't fully confirmed (a single snapshot reading, a loosely-timed
repeating pattern rather than a tight cluster, a metric that's abnormal but
not yet correlated to an actual failure).

### Tier 3: Root Causes (evidence directly supports the explanation)
For each Tier-1 anomaly, your best explanation of *why* it happened, built as
an **evidence chain** (not just an assertion) — e.g. install-date proximity →
position in a crash timeline → crash type → cascading pattern. State a
recommended action and a confidence percentage.

### Tier 4: Possible Root Causes (plausible, not fully confirmed)
For anomalies where you have a strong hypothesis but the available data
can't fully confirm it — state the hypothesis, **and explicitly state what
additional data or analysis would confirm it** (e.g. "parsing the actual
.dmp file with WinDbg," "a longer capture window," "correlating against a
log that had already rolled over by collection time"). This "what would
confirm it" statement is required, not optional — it's what separates a
real root-cause investigation from a guess.

### Format per finding (all four tiers)
```
<ID>. <Short title> — <Category>
Evidence (ranked):
  1. <specific fact, with the source file cited>
  2. <specific fact, with the source file cited>
  ...
Confidence: <percentage>% (<one line stating why this percentage, not another>)

[Root cause tiers only:]
Root cause: <explanation built from the evidence chain above>
Recommended action: <concrete, specific action — not "investigate further">

[Possible tiers only:]
Why "possible" not confirmed: <what's missing>
What would confirm it: <specific next step>
```

### A few hard rules for judging
- **Every evidence line must cite its source file.** An unsourced claim is
  not evidence.
- **Confidence percentages must be justified in one sentence**, not just
  stated. "90%" with no reasoning is worth less than "60%" with a clear
  reasoning statement.
- **Don't put a finding in Tier 1 if your own evidence includes a caveat.**
  If you're hedging in your own bullet points, it belongs in Tier 2 or 4.
- **A recommended action must be specific enough to act on** — "roll back
  driver X to version Y" beats "check the driver."
