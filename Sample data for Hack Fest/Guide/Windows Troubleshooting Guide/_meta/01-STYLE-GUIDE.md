# Encyclopedia Style Guide (Strict)

Every entry MUST follow this specification exactly. Entries that deviate fail review.

## 1. File naming
```
vol-<NN>-<slug>/ch<NN>-<slug>/<entry-id>--<slug>.md
Example: vol-02-event-ids/ch03-scm/V2.C3.E7000--service-failed-to-start.md
```
Chunked delivery may consolidate a chapter into one file; entry structure inside is unchanged.

## 2. Required front matter (YAML)
```yaml
---
entry_id: V2.C3.E7000
title: "SCM 7000: Service Failed to Start"
category: event-id            # one of: event-id | wer | concept | procedure | reference | tool
event:                        # ONLY for category: event-id — otherwise omit block
  id: 7000
  provider: "Service Control Manager"
  channel: System
  level: Error                # Critical | Error | Warning | Information | Verbose
severity_for_triage: high     # high | medium | low | informational
applies_to: ["Windows 10", "Windows 11", "Windows Server 2016+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    path: "<doc path if known>"
    license: "CC BY 4.0"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
status: draft                 # draft | reviewed | verified-on-hardware
---
```

## 3. Required sections, in this order

### `## Overview`
2–4 sentences. What this entry is and why a troubleshooter cares. No jargon
introduced without definition. Must be readable standalone.

### `## Historical / Technical Context`
When the mechanism appeared, what problem it was designed to solve, how it
evolved across Windows versions. For event IDs: which component emits it and
under what internal condition.

### `## Message Text & Fields` *(event-id and wer categories only)*
The verbatim message template with insertion strings marked `%1`, `%2`…,
followed by a table defining each field:

| Field | Meaning | Example |
|---|---|---|

### `## Meaning`
Plain-language interpretation: what the system is actually telling you.
Distinguish what the event *proves* from what it merely *suggests*.

### `## Likely Root Causes`
Ordered list, most common first. Each cause gets: mechanism (one sentence),
confirming evidence (what else you'd see), and prevalence note
(`very common` / `common` / `uncommon` / `rare`).

### `## Diagnostic Procedure`
Numbered steps. Every step that runs a command shows the exact command in a
fenced block with language tag (`powershell`, `cmd`, `text`). Commands must be
copy-paste safe: no smart quotes, no line-wrapped continuations without
backticks/carets. Read-only steps come before state-changing steps; the first
state-changing step is flagged **[MODIFIES SYSTEM]**.

### `## Resolution`
Fix per root cause, keyed to the Likely Root Causes list.

### `## Key Figures & Ecosystem` *(optional)*
Notable tools, authors, or documentation lineages relevant to the topic
(e.g., Sysinternals for process events, Randy Franklin Smith's encyclopedia
for Security log IDs). Reference, never reproduce, third-party content.

### `## Impact`
Operational consequence if ignored: data-loss risk, security exposure,
user-visible symptom, fleet-scale implications.

### `## Related Entries`
Bulleted `entry_id — title` cross-references. Minimum 2 where they exist.

### `## References & Attribution`
Every source, one per line:
`- <repo or publication> — <path/title> — License: <license> — retrieved <date>`
CC BY 4.0 sources MUST name the repository and state the license. Original
synthesis is marked as such. Never copy documentation text verbatim; all prose
is rewritten, with the source cited for attribution.

## 4. Prose rules
- Active voice; second person for procedures ("Run…", "Check…").
- Sentence-case headings. No heading deeper than `###` inside an entry.
- Numbers: event IDs and error codes in monospace: `7000`, `0x80070005`.
- Hex codes always 0x-prefixed, uppercase hex digits: `0xC0000005`.
- Registry paths in monospace, full hive names: `HKLM\SYSTEM\CurrentControlSet\...`
- Never claim certainty the evidence doesn't support: "indicates" vs. "proves".
- No filler ("it's important to note", "in today's world").

## 5. Tables
- Pipe tables only; header row required; no merged cells.
- Code inside tables uses single backticks.

## 6. Cross-references
- Always by `entry_id`, never by page number (pagination is a rendering concern).

## 7. Licensing invariants
- Each entry's front matter `sources` block is authoritative for that record.
- Aggregate license inventory lives in `V11.C1.E001` (Source Registry).
- Derived-from-CC-BY-4.0 content: retain attribution, note modifications
  ("adapted"), and do not imply Microsoft endorsement.
