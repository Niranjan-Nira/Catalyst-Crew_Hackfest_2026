# Labeled Dataset — Split by Category

The full `labeled_events_dataset.csv`/`.json` (162 rows, all 9 categories) is
still the main file for training a single model across all categories. This
folder splits it into **one file per category**, for anyone who wants to
build category-specific classifiers, or just wants to see one category's
criteria in isolation without scrolling through the rest.

Every file has identical columns to the combined dataset
(`event_id, device_id, category, label, confidence, confidence_reason,
description, source_file, evidence_detail, timestamp`) — only the row
selection differs.

| File | Rows | anomaly | possible_anomaly | not_anomaly |
|---|---|---|---|---|
| `app_stability.csv/json` | 114 | 32 | 24 | 58 |
| `correlation_cluster.csv/json` | 9 | 1 | 8 | 0 |
| `cpu_hardware.csv/json` | 9 | 0 | 7 | 2 |
| `disk.csv/json` | 7 | 1 | 0 | 6 |
| `driver_device.csv/json` | 9 | 7 | 0 | 2 |
| `memory_hardware.csv/json` | 4 | 0 | 3 | 1 |
| `reliability_onset.csv/json` | 8 | 0 | 7 | 1 |
| `system_stability.csv/json` | 1 | 1 | 0 | 0 |
| `update_failure.csv/json` | 1 | 0 | 1 | 0 |

---

## The exact "how do you know" criteria per category

This is the part that matters most: for each category, what specifically
makes a row `anomaly` vs. `possible_anomaly` vs. `not_anomaly`. (Full worked
examples with real data are in `DATASET_METHODOLOGY.md` — this table is the
quick-reference version.)

### `app_stability.csv`
- **`anomaly`** — the same (process, crash-type) pair recurs **3 or more
  times**. 5+ times = 90% confidence; 3-4 times = 75%.
- **`possible_anomaly`** — the pair occurs **exactly 2 times**. Confidence
  50% — could be a real pattern or two unrelated one-offs.
- **`not_anomaly`** — the pair occurs **exactly once**. Confidence 55% — a
  single crash is normal background noise, not evidence of a systemic issue.

### `correlation_cluster.csv`
- **`anomaly`** — **4 or more distinct processes** (not the same process
  repeated) crash within a 180-second window. 6+ distinct = 90%; 4-5 = 80%.
- **`possible_anomaly`** — only **2-3 distinct processes** in the window —
  suggestive but too small a sample to rule out coincidence (45%).
- **`not_anomaly`** — not generated for this category; if there's no
  cluster, there's simply no row (absence of a row here means no finding,
  not a confirmed-healthy claim).

### `cpu_hardware.csv`
- **`anomaly`** — a WHEA or throttling event logged at `Error`/`Critical`
  severity (85%). *(None of the 5 devices had this — see below.)*
- **`possible_anomaly`** — an event present but only at non-error severity,
  OR (Device 2 only) more than 3 live-capture samples above 90°C (40-50%).
- **`not_anomaly`** — no qualifying events found at all (85%), or CPU
  temperature data was present but entirely null/unreadable (40% — a weaker
  claim, since "no data" isn't the same certainty as "confirmed normal").

### `disk.csv`
- **`anomaly`** — `PercentFree < 5`, OR SMART `PredictFailure == True`, OR
  `HealthStatus` is not `"Healthy"`, OR 30+ IO retry/warning events (75-95%
  depending on which rule fired).
- **`possible_anomaly`** — `PercentFree` between 5-15%, or 10-29 IO retry
  events (50-55%). *(No rows landed here in this specific dataset — all 5
  devices were either clearly healthy or, in one case, clearly high-retry.)*
- **`not_anomaly`** — `PercentFree ≥ 15`, `HealthStatus == "Healthy"`,
  `PredictFailure == False`, or fewer than 10 retry events (60-90%).

### `driver_device.csv`
- **`anomaly`** — a real, non-blank `ConfigManagerErrorCode` in
  `DevicesWithConfigManagerErrors.csv`, OR a currently-present device with a
  non-OK `Status`. Confidence 65% if the device is a known-benign class
  (Bluetooth/virtual peripheral), 80-85% for core hardware.
- **`possible_anomaly`** — not currently used for this category; a device
  error code is treated as binary (present = anomaly, absent = not).
- **`not_anomaly`** — no rows in the config-manager-error file, or no
  present device with non-OK status (85% / 80%).

### `memory_hardware.csv`
- **`anomaly`** — a WHEA memory event at `LevelDisplayName == "Error"` or
  `"Critical"` (88%). *(None of the 5 devices had this.)*
- **`possible_anomaly`** — a WHEA memory event present but only at
  `"Information"` level (40%) — **this is the category where severity-level
  checking mattered most**; see `DATASET_METHODOLOGY.md` for the full story
  of why this isn't just "any row = anomaly."
- **`not_anomaly`** — no WHEA memory events found at all (85%).

### `reliability_onset.csv`
- **`possible_anomaly`** only — a day-over-day stability score drop greater
  than 2 points (55%). This category is deliberately never `anomaly` — it
  marks *when*, not *why*, so it can't stand alone as a confirmed finding.
- **`not_anomaly`** — no qualifying drop found across the recorded window (70%).

### `system_stability.csv`
- **`anomaly`** — Kernel-Power Event ID `41` present (unexpected
  shutdown/reboot) (80%).
- **`not_anomaly`** — no such event found (80%). *(This category only exists
  for Device 2's schema — the other 4 devices' collector doesn't capture
  boot/shutdown history the same way, so they have no rows here at all.)*

### `update_failure.csv`
- **`possible_anomaly`** only — 3 or more update installation failures in
  the reliability history (55%). Capped at `possible_anomaly` because a
  failed update alone doesn't prove ongoing harm without further correlation.

---

## A note on categories with no `anomaly` rows in THIS dataset

`cpu_hardware`, `memory_hardware`, `reliability_onset`, and `update_failure`
have zero rows labeled plain `anomaly` (only `possible_anomaly` and
`not_anomaly`) across these specific 5 devices. This is an honest property
of this particular dataset — none of these 5 machines happened to have a
severe, unambiguous case in those categories — **not** a sign that those
categories can never reach `anomaly`. The rules support it (see the
thresholds above); this data just didn't trigger it. If you train a
classifier only on this data, be aware it has not seen a positive
high-confidence example for those categories, and may need synthetic
examples or a wider dataset to learn that class properly.


## `labeled_events_dataset.csv` / `.json` — schema

| Column | Meaning |
|---|---|
| `event_id` | Unique row identifier (`EVT00001`, ...) |
| `device_id` | Which of the 5 devices this finding came from |
| `category` | One of: `disk`, `memory_hardware`, `cpu_hardware`, `driver_device`, `app_stability`, `correlation_cluster`, `reliability_onset`, `system_stability`, `update_failure` |
| `label` | **The target variable.** `anomaly`, `possible_anomaly`, or `not_anomaly` |
| `confidence` | 0-100, how confident the rule-based labeler is in this specific label |
| `confidence_reason` | One sentence stating *why* — every confidence score is justified, not just asserted |
| `description` | Plain-English summary of the finding |
| `source_file` | Which raw log file this was extracted from (so you can always trace back to ground truth) |
| `evidence_detail` | The specific value(s)/row that produced this finding |
| `timestamp` | When the underlying event occurred, if known |

**162 total rows** across 5 devices: **42 `anomaly`, 50 `possible_anomaly`, 70
`not_anomaly`.** `not_anomaly` rows are deliberately included — a model that
never sees negative/healthy examples can't learn what "normal" looks like.

---

## `case_analysis_all_devices.csv` / `.json` — schema

| Column | Meaning |
|---|---|
| `case_id` | Unique row identifier |
| `device_id` | Device this case belongs to (or `FLEET` for the cross-device finding) |
| `tier` | `anomaly`, `possible_anomaly`, `root_cause`, or `possible_root_cause` |
| `category` | Same category taxonomy as the events dataset |
| `title` | The finding, phrased as a headline |
| `evidence` | Supporting facts, each traceable to a source file |
| `confidence_pct` | Justified confidence score |
| `confidence_reason` | Why that score, not another |
| `root_cause` | The explanation, where the tier is a root-cause tier |
| `recommended_action` | Concrete next step |
| `why_not_confirmed` | For `possible_*` tiers — what's missing |
| `what_would_confirm` | For `possible_*` tiers — what data/analysis would resolve the gap |

---

## How the labels were actually decided (methodology, not a black box)

Two source schemas were involved — Devices 1, 4, 5, 6 came from the standard
17-module DiagCollector; **Device 2 came from a different collector entirely**
(its own folder layout: `Battery/`, `DiskHealth/`, `Drivers/`, `EventLogs/`,
etc., with extra data the other tool doesn't capture — live fan RPM and CPU
temperature, boot/shutdown history, before/after process snapshots). Both were
normalized into the same output schema via two separate adapter functions in
`build_dataset.py` (`analyze_standard()` and `analyze_alt()`), so the labeled
dataset itself is schema-agnostic even though the raw inputs weren't.

**Every rule follows the same pattern:** read a specific file/field → apply an
explainable threshold or presence check → assign a label and a confidence
with a stated reason. A sample of the actual rules:

- **Disk free space:** `<5%` free → `anomaly` (90%); `<15%` → `possible_anomaly`
  (55%); otherwise `not_anomaly` (90%).
- **WHEA hardware memory/CPU errors:** tiered by `LevelDisplayName`. Rows at
  `Error`/`Critical` severity → `anomaly` (85-88%). Rows present but only at
  `Information` severity → `possible_anomaly` (40%) — **this distinction
  matters**: Devices 4 and 6 both have WHEA memory events, but all of them are
  `Information`-level, so they're correctly labeled `possible_anomaly`, not
  `anomaly`. Treating "any row present" as automatically high-confidence would
  have been wrong here.
- **Config Manager device errors:** `anomaly`, but confidence is split —
  85% for core hardware (NICs, storage, firmware), only 65% for
  minor/virtual peripherals (e.g. Bluetooth virtual COM ports), since the
  latter fail to start harmlessly on many machines.
- **Recurring crash/hang signatures (WER):** grouped by (process, crash-type)
  pair. 5+ occurrences → `anomaly` (90%); 3-4 → `anomaly` (75%); exactly 2 →
  `possible_anomaly` (50%); a single occurrence → `not_anomaly` (55%) — one
  crash is normal background noise on any Windows machine.
- **Cross-process correlation clusters:** all crash timestamps across a
  device are sorted chronologically; 4+ genuinely distinct processes crashing
  within a 180-second window → `anomaly` (80-90%, scaled by process count).
  2-3 distinct processes in a similar window → `possible_anomaly` (45%) only,
  since a small sample can't rule out coincidence.
- **SMART failure prediction (Device 2 only):** the drive's own firmware
  reporting `PredictFailure=True` → `anomaly` at 95% — about as authoritative
  as disk evidence gets.
- **Unexpected shutdown (Kernel-Power Event ID 41, Device 2 only):** → `anomaly`
  (80%) — a well-documented signature for a hang requiring a hard reset or a
  power-loss event.

### Root-cause matching (Tier 3/4) 

For each correlation-cluster anomaly, the pipeline searches installed
applications within 45 days prior and tries to match one to the actual
crashed processes — **not just "whatever was installed most recently."**

The first version of this logic picked the *nearest-dated* install
regardless of relevance, and on Device 1 it initially matched an unrelated
Python installation instead of the real lead. Root cause of that bug: it was
matching against bare executable names (`spksvc.exe`), which often don't
resemble a vendor's marketed product name (`Spektion Sensor`). The fix:
match against each crashed process's **install folder path** (`AppPath`,
e.g. `...\Spektion\Spektion Sensor\spksvc.exe`), which does contain the real
vendor name — and exclude a stopword list of generic terms (`Microsoft`,
`Windows`, `Service`, `Management`, etc.) that would otherwise match almost
anything and produce false leads. After the fix, Device 1's cluster
correctly surfaces `Spektion Sensor` (installed 9 days before the crash
cluster) as the possible-root-cause candidate, at only 50% confidence — a
real match, but still correctly labeled circumstantial, not proven.
**This is left in the README deliberately**, not because you need to know
the bug, but so participants trust that this dataset was actually verified
against known-correct answers, not just generated and shipped.

---

## The fleet-wide finding 

The identical failure signature (`StoreAgentInstallFailure1`,
`StoreAgentScanForUpdatesFailure0`, Microsoft Edge Updater `crashpad_log`
crashes) appears **independently on 4 of the 5 devices** (`device_01`,
`device_04`, `device_05`, `device_06`) with occurrence counts ranging from 9
to 60. This is filed as a `FLEET`-level `possible_root_cause` case at 60%
confidence: the same signature recurring across unrelated machines is much
stronger evidence of a systemic cause (shared OS build, shared deployment
image, or a network/proxy restriction on update servers) than any single
device's occurrence alone — but it still doesn't pinpoint *which* shared
factor is responsible, so it's correctly a `possible_root_cause`, not a
confirmed one.

---

## Known limitations 

- **This is a rule-based labeler, not hand-verified row by row.** Every
  category of rule was spot-checked against the raw source files (and one
  real bug was caught and fixed — see above), but with 162 rows across 5
  devices, individual rows were not all manually re-verified. Treat this as
  strong, explainable ground truth — not as infallible.
- **Tier 3 (`root_cause`, near-certain) has zero entries in this dataset.**
  None of these 5 devices happened to have a SMART failure prediction or a
  critically-low disk — the two rules currently wired to produce a Tier-3
  finding. This is an honest property of this specific dataset, not a bug in
  the pipeline — the schema supports Tier 3, this data just didn't reach that
  bar anywhere.
- **Driver-version/install-date cross-referencing for `driver_device`
  anomalies was not automated** in this pass — those cases are filed as
  `possible_root_cause` with an explicit note that the check wasn't run, so
  it's flagged as a gap rather than silently skipped.
- **Device 2's raw `.evtx` event logs were not parsed** — only its
  pre-extracted CSVs were used. Device 2 also has no WER crash-dump folder at
  all (different collector, different capture strategy), so correlation-
  cluster detection (which depends on WER) naturally produced no findings for
  that device — this is a genuine gap in what that collector captured, not
  something this pipeline failed to find.
- **`bad_module_info` appearing as a "process name"** in a couple of Device 5
  findings is not a parsing bug — it's Windows' own literal crash-log text
  when it couldn't resolve the actual faulting module. Left as-is rather than
  filtered out, since it's genuine (if unhelpfully named) raw evidence.

---


