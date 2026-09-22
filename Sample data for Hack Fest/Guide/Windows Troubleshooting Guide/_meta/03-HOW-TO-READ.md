# How to Read This Encyclopedia

**Curated by Joe Prakash**

This document explains how the encyclopedia is built, so you can navigate it
by hand — before the next document covers turning it into a database an AI
can query.

---

## 1. The unit of information is the "entry," not the file

Each chapter file (e.g. `vol-02-event-ids/ch03-service-control-manager.md`)
contains several **entries** concatenated together, separated by `---`. An
entry is one self-contained topic — one event ID, one procedure, one concept.
Each entry has:

```yaml
---
entry_id: V2.C3.E7000
title: "SCM 7000: Service Failed to Start"
category: event-id
event: { id: 7000, provider: "Service Control Manager", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources: [...]
last_reviewed: 2026-08-30
curator: Joe Prakash
status: draft
---
```

followed by fixed sections: **Overview → Historical/Technical Context →
Message Text & Fields → Meaning → Likely Root Causes → Diagnostic Procedure →
Resolution → Impact → Related Entries → References & Attribution.**

The `entry_id` (`V<volume>.C<chapter>.E<id>`) is the addressable unit —
cross-references throughout the encyclopedia point to entry IDs, never to page
numbers or filenames. If you're told "see V3.C1.E006," open that volume's
chapter and search for `entry_id: V3.C1.E006`.

## 2. Reading paths, by what you're holding

**You have an event ID and nothing else** (e.g. you saw "Event 7000" in
Event Viewer): go to the Master TOC (`_meta/00-MASTER-TOC.md`), find the entry
under the matching volume/chapter, and jump to it. Read **Meaning** first (what
it proves vs. suggests), then **Likely Root Causes** (ordered by prevalence),
then **Diagnostic Procedure** for the exact commands.

**You have a symptom, not an ID** (e.g. "machine is slow to boot"): start at
the Master TOC's volume list, not the event-ID volume — Volumes I (Foundations),
IX (Performance), and X (App Compatibility) are organized by symptom, not ID,
and will route you to specific event IDs via their **Related Entries** sections.

**You have a WER report or a dump**: go to Volume III directly — Chapter 1
decodes `Report.wer` field by field; Chapter 2 is the WinDbg workflow.

**You're building a fleet-wide investigation**: start at Volume I Chapter 1
(the discipline) and Chapter 3 (the toolbox) — they're the methodology that
the rest of the volumes assume you're using.

## 3. Follow "Related Entries" — the encyclopedia is a graph, not a list

No entry is meant to be read in isolation. A storage failure entry
(`V2.C4.E007`) links forward to the paging-error entry (`V2.C4.E051`), sideways
to the WER exception-code table (`V3.C1.E006`), and backward to the
architecture chapter explaining the storage stack (`V1.C2.E005`). Real
incidents usually require walking two or three linked entries, not one.

## 4. Trust the `severity_for_triage` and `status` fields

`severity_for_triage` (`high`/`medium`/`low`/`informational`) tells you how
urgently a finding deserves action — use it to triage when several entries
match a symptom at once. `status: draft` (currently every entry in this
edition) means: directionally correct, curated from documentation and field
knowledge, but **not yet independently verified against a live failure on your
hardware**. Treat commands under `[MODIFIES SYSTEM]` with the caution that
label implies, and verify a `draft` entry's specific claims before relying on
it in a production incident.

## 5. Copy commands exactly; read tables as decision logic, not trivia

Every code block is meant to be run as shown — PowerShell blocks use the
XML-field-extraction idiom (`([xml]$e.ToXml()).Event.EventData.Data`)
throughout so they survive locale differences; don't substitute
`.Message`-parsing unless the entry says to. Reference tables (error-code
atlases, logon-type tables, stop-code families) are decision tools: find your
specific code/type/ID as a **row**, and let that row's "first move" or "story"
column tell you what to do next — don't read them start to finish.

## 6. The licensing layer matters if you redistribute

Every entry's `sources` front matter states what it draws on and under what
license (see `_meta/02-SOURCES-AND-LICENSING.md`, Volume XI). If you quote or
republish an entry outside your own team, carry that attribution with it.
