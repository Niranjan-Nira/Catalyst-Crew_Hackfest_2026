# Participant Documentation Package — Index

This package answers the questions raised after the raw logs and the first
labeled dataset were shared. Read in this order:

## Approved resource policy

See `FREE_LOCAL_RESOURCES.md` for the free local datasets, reference material,
offline retrieval path, and network policy. Luna is the only optional model
endpoint; raw case logs are not automatically indexed as global knowledge.

## 1. `ANOMALY_INVESTIGATION_GUIDE.md`
**Start here.** Answers: where do I check first and what does it lead to,
what are the anomaly categories and how do they connect, where do I go to
verify a specific claim, which part of a huge log message actually matters,
what do the codes/timestamps mean, and what's actually important out of
everything collected.

## 2. `DATASET_METHODOLOGY.md`
Answers exactly how `labeled_events_dataset.csv` was built — for every
category, which file, which field, what real value was seen, and how that
became a label and confidence score. Includes the story of a real mistake
(a wrong root-cause match) that was caught and fixed, so you can see the
verification process, not just the output.

## 3. `labeled_by_category/`
The same 162 rows as the combined dataset, split into one CSV+JSON pair per
category, with a README stating the exact anomaly / possible-anomaly /
not-anomaly criteria for each category individually.

## 4. `COMMON_ANOMALY_CATALOG.md`
Anomaly patterns that are well-documented in Windows generally but did NOT
happen to appear in these 5 sample devices — use this so your model/process
can recognize a genuinely new device's issue, not just memorize these 5.

---

## Quick answers to the numbered questions, with a pointer to the full answer

1. **Where to check first / what leads to what** → Investigation Guide, Section 1
2. **Categories of anomaly and how they connect** → Investigation Guide, Section 2
3. **Where to verify a claim, which part of the file** → Investigation Guide, Section 3
4. **Which part of a long message matters** → Investigation Guide, Section 4
5. **What codes/timestamps mean** → Investigation Guide, Section 5
6. **What's actually important in the volume of logs** → Investigation Guide, Section 6
7. **How the labeled dataset was built, file by file** → Dataset Methodology (full document)
8. **Per-category labeled dataset, with anomaly/not-anomaly criteria** → `labeled_by_category/`
9. **How an Event ID's meaning was determined (e.g. 1000 = crash)** → Investigation Guide, Section 5 (Event ID table) — sourced from Microsoft's own documented Event IDs where confidence is marked High, with an explicit note where a specific numeric ID should be double-checked against Microsoft Learn rather than taken as memorized fact
10. **Other common anomalies for generalizing to a new device** → `COMMON_ANOMALY_CATALOG.md`
