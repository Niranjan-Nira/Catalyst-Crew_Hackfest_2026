## A. Where to start across 17 folders — don't read them in order

You do **not** need to open every folder top-to-bottom. Folders are numbered
for organization, not for the order you should investigate them in. Use this
funnel instead:

### Step 1 — Always start here (2 files)
- `_StatusReport\StatusReport.txt` — confirms what data you can trust.
- `09_ReliabilityMonitor\StabilityIndex_DailyScore.csv` — tells you **which
  date(s)** to focus on. A machine with no dip in this score probably has
  nothing dramatic to find; a sharp drop tells you exactly where to look next.

### Step 2 — Check the "presence = signal" files (5 files)
These are files where an empty result is genuinely good news, so you can
rule categories in or out fast:
- `04_HardwareDevices\DevicesWithConfigManagerErrors.csv`
- `06_Memory\WHEA_HardwareMemoryErrors.csv`
- `07_CPU\CPU_WHEA_Errors.csv` and `CPU_ThrottlingEvents.csv`
- `16_Services_Processes\AppCrashHang_PersistentHistory.csv`

Whichever of these is **non-empty** tells you which deep-dive folder to go to
next. If all of them are empty, the issue (if any) is likely a live/transient
one — go straight to `01_Timeline_And_Resources` instead.

### Step 3 — Deep-dive only the folder(s) Step 2 pointed you to
- Non-empty device errors → go deep on `04_HardwareDevices` +
  `08_SystemInfo\AllDrivers_VersionDate.csv` (driver version/date).
- Non-empty memory/CPU hardware errors → go deep on `06_Memory` / `07_CPU`.
- Non-empty crash history → go to `15_CrashDumps_WER` and group by process
  name and `EventType` (see Part A above).
- Nothing pointed anywhere → go to `01_Timeline_And_Resources` for the live
  30-minute capture and look for a resource spike or a "stopped" process
  event with no obvious user action behind it.

### Step 4 — Only pull in the "supporting context" folders once you have a lead
Don't open these speculatively — only once Steps 1–3 give you a specific
hypothesis to check against:
- `03_WindowsUpdates` — did an update/KB install right before the issue?
- `14_InstalledApps` — was something new installed right before?
- `12_Network`, `13_AppLogs`, `10_Battery`, `11_StartupApps` — only relevant
  if your hypothesis specifically points there (e.g. a "Net" class device
  error → check `12_Network`; a VPN client suspected → check `13_AppLogs`).


> "You don't read 17 folders. You read 2 files to find *when*, 5 files to
> find *what category*, then you go deep on exactly one or two folders. The
> rest of the folders are there to confirm your hypothesis once you already
> have one — not to browse from the start."
