# How the Labeled Dataset Was Actually Built

This answers directly: **which files were checked, which specific field in
each file, what that field's value means, and how that turned into a label.**
Nothing here is abstract — every rule below is the literal logic used, with
a real example from the actual device data.

The full code is in `build_dataset.py` and `build_case_report.py` — this
document is the human-readable walkthrough of what that code does and why.

---

## The general method (applies to every category)

For every category, the same 4-step process was followed:

1. **Pick the file(s) that contain ground truth for this category** (not
   guesswork — Windows itself already tracks most of this; e.g. disk free
   space is a fact Windows reports directly, not something to infer).
2. **Pick the exact column/field that carries the signal.**
3. **Apply a threshold or presence rule to that field** — written down
   explicitly, not a "feels like an anomaly" judgment call.
4. **Assign a label and confidence, with the reason spelled out** — so the
   label can be checked and disputed, not just trusted.

Below is that process for every category, in the same order as the dataset.

---

## `disk`

**File(s) checked:**
`05_Disk/Drives_SizeFreeSpace.csv` (standard schema) or
`DiskHealth/PhysicalDiskHealth.csv` + `SMART_FailurePredictStatus.csv` +
`DiskRelatedEvents.csv` (Device 2's schema).

**Field checked:** `PercentFree` (a number), `HealthStatus` (text: "Healthy"
or not), `PredictFailure` (`True`/`False`), and a row count of
`DiskRelatedEvents.csv`.

**Real example:** Device 1's `Drives_SizeFreeSpace.csv` had
`PercentFree` well above 15% → labeled `not_anomaly`, confidence 90%,
reason: "Comfortably above the low-space caution threshold."

**The actual thresholds used:**
- `PercentFree < 5` → `anomaly` (90%) — below 5% reliably causes save/update
  failures.
- `PercentFree < 15` → `possible_anomaly` (55%) — a caution zone, not yet
  critical.
- `PredictFailure == True` → `anomaly` (95%) — the drive's own firmware
  making a failure prediction is about as direct as disk evidence gets.
- `DiskRelatedEvents.csv` row count ≥ 30 → `anomaly` (75%); ≥ 10 →
  `possible_anomaly` (50%); some sub the drive's own retry mechanism is
  working normally at low volume → `not_anomaly`.

**Why these specific numbers?** 5%/15% are common IT operational
thresholds (not something Windows defines internally) — they're a judgment
call, disclosed as such rather than presented as an official Microsoft
number. Participants are free to argue for different thresholds; the point
is that a threshold exists and is stated, not that this exact number is
sacred.

---

## `memory_hardware`

**File checked:** `06_Memory/WHEA_HardwareMemoryErrors.csv`

**Field checked:** `LevelDisplayName` — specifically, **not just whether the
file has rows**, but whether those rows say `Error`/`Critical` or only
`Information`.

**Real example (Device 4):**
```
TimeCreated: 8/4/2026 7:29:01 AM
Id: 3
LevelDisplayName: Information
Message: A hardware event has occurred. An informational record
         describing the condition is contained in the data section
         of this event.
```
This row exists (the file is not empty) but `LevelDisplayName` is
`Information`, not `Error`. **Label: `possible_anomaly`, confidence 40%.**
Reason given: "present but logged at Information level only — Windows
itself did not classify these as faults."

**Why this distinction matters:** an earlier, cruder version of this rule
(used in a single-device walkthrough earlier in this project) treated "any
row in this file" as automatically high-confidence. Checking the actual
`LevelDisplayName` field on Devices 4 and 6 showed that assumption would
have been wrong here — both devices' WHEA rows are informational, not
confirmed faults. **This is exactly why the rule reads the severity field
instead of just counting rows.**

If a device instead has `LevelDisplayName == "Error"` or `"Critical"` →
`anomaly`, confidence 88%, because that IS Windows' own hardware layer
explicitly flagging a fault, not just logging a record.

---

## `cpu_hardware`

**Files checked:** `07_CPU/CPU_WHEA_Errors.csv`, `07_CPU/CPU_ThrottlingEvents.csv`,
or (Device 2) `Timeline_Thermal_Power_Fan/ThermalPowerFan.csv`.

**Field checked:** Same `LevelDisplayName` logic as memory, OR (Device 2
only) the numeric `CPU_Temp_C` column.

**Real example:** all 5 devices had CPU_WHEA/Throttling files that were
either empty or non-Error severity → every one of these landed as
`not_anomaly` or `possible_anomaly`, never a high-confidence `anomaly`, for
this category across this specific dataset. (Device 2's thermal file also
had mostly-null `CPU_Temp_C` values — the sensor wasn't accessible — logged
as `not_anomaly` at only 40% confidence, since "no data" is a weaker claim
than "confirmed normal.")

---

## `driver_device`

**File checked:** `04_HardwareDevices/DevicesWithConfigManagerErrors.csv`
(standard schema) — **specifically NOT** `ProblemDevices_ONLY.csv`, which
was checked and found to be ~95% `CM_PROB_PHANTOM` entries (unplugged USB
peripherals — normal, not a fault) across all 4 standard-schema devices.

**Field checked:** `ConfigManagerErrorCode` (any non-blank value in this
specific file counts, since this file is pre-filtered by Windows to only
real, non-phantom errors).

**Real example (Device 1):**
```
Name: Intel(R) Ethernet Connection (24) I219-LM
ConfigManagerErrorCode: CM_PROB_FAILED_POST_START
```
→ `anomaly`, confidence 85%.

**Confidence was NOT flat across all rows in this category** — Device 4 had:
```
Name: Standard Serial over Bluetooth link (COM4)
ConfigManagerErrorCode: CM_PROB_FAILED_START
```
This got only **65%** confidence, not 85%, because a regex check
(`bluetooth|virtual|COM\d` against the device name) flagged it as a
minor/virtual peripheral class known to fail to start harmlessly on many
systems — a real error code, but lower real-world impact than a core NIC
failing.

---

## `app_stability`

**File checked:** `15_CrashDumps_WER/<folder>/Report.wer` (every folder,
decoded — see the Investigation Guide Section 4 for the decode method), plus
`16_Services_Processes/AppCrashHang_PersistentHistory.csv` for independent
corroboration.

**Field checked:** `EventType=` and the process name guessed from the
folder name, grouped together, then **counted**.

**Real example (Device 1):**
7 `Report.wer` folders decoded, grouped by `(process, EventType)`. One group:
`OFFICE_MODULE_VERSION_MISMATCH` for `POWERPNT.EXE` appeared **3 times** →
`anomaly`, confidence 75% (the 3-4 occurrence bucket; 5+ occurrences would
have scored 90%).

**The exact count-to-confidence rule used:**
- 5+ occurrences of the identical `(process, EventType)` pair → `anomaly` (90%)
- 3-4 occurrences → `anomaly` (75%)
- exactly 2 → `possible_anomaly` (50%) — "could be a repeating issue or two
  unrelated one-offs; not enough volume to be confident"
- exactly 1 → `not_anomaly` (55%) — "a single crash/hang event is common
  background noise on any Windows machine"

**Why count-based, not just presence-based?** A single app crash happens on
healthy machines too. The dataset does NOT label every crash `anomaly` —
only recurring ones. This is the single most important design choice in
this category.

---

## `correlation_cluster`

**File checked:** the same `Report.wer` files as `app_stability` — **but
processed completely differently**: instead of grouping by process, every
decoded crash's `EventTime` (converted from FILETIME — see Investigation
Guide Section 5) across the WHOLE device is sorted chronologically, and the
code looks for windows where several **different** processes fall within
180 seconds of each other.

**Real example (Device 1):** 7 distinct processes
(`spksvc.exe, AppUp.IntelArcSo, Microsoft.Paint, SenseTracer.exe,
BtSystem.Service, Licensing.Servic, dwm.exe`) all crashed within 105
seconds (decoded times: 12:51:58 through 12:53:43) → `anomaly`, confidence
90%. Reason: "7 unrelated processes failing within 105 seconds is far more
consistent with a shared trigger... than independent coincidence."

**The count-to-confidence rule:**
- 6+ distinct processes in the window → 90%
- 4-5 distinct processes → 80%
- only 2-3 distinct processes → `possible_anomaly` only, 45% — small sample,
  coincidence can't be ruled out.

---

## `reliability_onset`

**File checked:** `09_ReliabilityMonitor/StabilityIndex_DailyScore.csv`

**Field checked:** `SystemStabilityIndex`, compared day-over-day (each row's
value minus the *previous* row's value).

**Rule:** a drop greater than 2 points between consecutive days →
`possible_anomaly`, confidence 55% — always `possible_anomaly`, never
higher, because (as stated in every one of these findings) "a sharp
day-over-day drop marks WHEN instability began but doesn't by itself
identify WHY."

This category is intentionally capped at `possible_anomaly` — it is a
pointer to investigate elsewhere, never treated as a conclusion on its own.

---

## `system_stability` (Device 2 schema only)

**File checked:** `BootShutdownHistory/BootShutdownEvents_KernelPower.csv`

**Field checked:** `Id` column, specifically the literal value `41`.

**Real example:**
```
Id: 41, LevelDisplayName: Critical
Message: The system has rebooted without cleanly shutting down first.
         This error could be caused if the system stopped responding,
         crashed, or lost power unexpectedly.
```
5 such rows found on Device 2 → `anomaly`, confidence 80%. This specific
Event ID is a well-documented Windows signature (see the Investigation
Guide's Event ID table) for exactly this scenario, which is why the
confidence is high without needing further corroboration.

---

## `update_failure`

**File checked:** `ReliabilityHistory/ReliabilityRecords.csv` (Device 2)

**Field checked:** `Message` column, text-matched for
`"Installation Failure"`, `"failed to install"`, or `"error 0x"`.

**Rule:** 3+ matching rows → `possible_anomaly`, confidence 55%. Capped at
`possible_anomaly` because a failed update alone doesn't prove ongoing harm
— it needs correlation with an actual instability window to become more
confident.

---

## How the ROOT CAUSES (Tier 3/4) were built — the harder part

Anomalies (Tier 1/2) are checked directly against a file. Root causes are
**inferred by cross-referencing two different files' timestamps.**

**Real example — Device 1's correlation cluster:**
1. Take the cluster's timestamp (2026-08-07 12:51:58, from Step above).
2. Open `14_InstalledApps/InstalledApplications_Registry.csv`, filter to
   installs within 45 days before that timestamp.
3. **Naive approach (tried first, and wrong):** just pick whichever install
   is closest in date. This actually picked an unrelated Python installation
   the first time this was run — wrong lead.
4. **Fixed approach:** instead of matching by date alone, match the
   candidate app's `DisplayName` against the crashed processes' **install
   folder paths** (`AppPath`, e.g.
   `C:\Program Files\Spektion\Spektion Sensor\spksvc.exe`), which contain the
   real vendor name — not the bare executable name, which often doesn't
   resemble it. A stopword list (`Microsoft`, `Windows`, `Service`, etc.)
   excludes overly generic words that would match almost anything.
5. Result: `Spektion Sensor`, installed 9 days before the cluster, correctly
   surfaces as the candidate — **at only 50% confidence**, explicitly
   labeled `possible_root_cause`, not `root_cause`, because install-timing
   proximity (even a real name match) is circumstantial, not proof.

This is the most important lesson in the whole methodology: **a root-cause
match needs to connect to the SPECIFIC evidence (which processes actually
crashed), not just "what's nearby in time."** Date-proximity alone produces
false leads.

---

## Where confidence numbers come from — the honest answer

There is no formula that outputs "72.3%." Every confidence number in this
dataset is a **discrete tier**, chosen by matching the evidence strength to
one of a small number of bands, each with a written justification:

| Band | When used |
|---|---|
| 90-95% | Authoritative single source (SMART prediction, a well-documented Event ID) OR a high-count recurring pattern |
| 80-88% | Strong, specific evidence (Error/Critical-level WHEA, a real Config Manager code) |
| 70-75% | A real pattern but below the highest-count threshold |
| 50-65% | A real but small/ambiguous signal, or a plausible but unconfirmed root-cause lead |
| 40-45% | Present but weak/unconfirmed — informational-only severity, or a small cluster |
| 25-30% | A stated hypothesis with no supporting evidence found, kept only to show the check was performed |

Participants building their own ML pipeline are not expected to reproduce
these exact numbers — they're expected to reproduce the **discipline**:
every confidence claim traces to a specific, nameable reason.
