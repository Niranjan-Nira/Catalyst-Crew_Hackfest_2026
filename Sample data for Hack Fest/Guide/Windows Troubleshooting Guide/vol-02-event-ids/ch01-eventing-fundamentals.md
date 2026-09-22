# Volume II · Chapter 1 — How Windows Eventing Actually Works

---
entry_id: V2.C1.E001
title: "Why 'All Event IDs Ever' Cannot Exist: The Provider-Manifest Model"
category: concept
severity_for_triage: informational
applies_to: ["Windows Vista+", "Windows Server 2008+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Event IDs in Windows are not globally unique. An ID is only meaningful in
combination with its **provider** (the component that emits it). Event ID
`7000` from Service Control Manager means "service failed to start"; event
`7000` from some other provider can mean something entirely unrelated. There is
therefore no finite, canonical list of "all event IDs" — there is a list of IDs
*per provider*, defined in that provider's manifest, and providers number in
the thousands across Windows versions, roles, drivers, and third-party software.

## Historical / Technical Context
Before Windows Vista, "classic" event logging (the ELF/EventLog API) used
message DLLs registered under
`HKLM\SYSTEM\CurrentControlSet\Services\EventLog\<log>\<source>`. Vista
introduced the unified ETW-based eventing model: each modern provider ships an
XML **instrumentation manifest**, compiled into a binary and registered with
the system. The manifest declares every event the provider can raise — its ID,
version, level, keywords, task, opcode, channel, and message template. The
message strings themselves live in localized `.mui` message resources next to
the owning binary. This is why the same event renders in the user's display
language, and why "the list of all events" is really "the union of all
registered manifests on a given machine at a given patch level."

## Meaning
Practical consequences for a troubleshooter:
1. Always record **Provider + Channel + ID**, never the ID alone.
2. Two machines can disagree about what an ID means if different software is
   installed — the manifest travels with the software.
3. The authoritative definition of any event is extractable locally
   (see `V2.C1.E004`); documentation is a secondary source.
4. IDs are versioned. Microsoft occasionally changes an event's fields between
   Windows releases while keeping the ID (the manifest `version` attribute
   increments).

## Impact
Triage automation keyed on ID alone produces false matches across providers.
Any collector (including fleet diagnostic tooling) should store the
provider name and channel with every event record.

## Related Entries
- V2.C1.E002 — Anatomy of an Event
- V2.C1.E004 — Enumerating Every Provider and ID on a Machine

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — event logging concepts — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — practical consequences analysis — License: n/a

---
entry_id: V2.C1.E002
title: "Anatomy of an Event: Provider, ID, Level, Keywords, Task, Opcode"
category: concept
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Every modern Windows event carries a fixed **System** block (who/when/where)
and a variable **EventData/UserData** block (the payload). Reading events well
means knowing which System fields carry diagnostic weight.

## Message Text & Fields
| Field | Meaning | Diagnostic weight |
|---|---|---|
| `Provider` | Component that raised the event (name + GUID) | Essential — disambiguates the ID |
| `EventID` | Provider-scoped identifier | Essential |
| `Version` | Schema version of this event | Matters when parsing EventData positionally |
| `Level` | 1 Critical, 2 Error, 3 Warning, 4 Information, 5 Verbose | Triage priority |
| `Task` / `Opcode` | Sub-area of the provider / operation phase (start/stop) | Useful for correlating operations |
| `Keywords` | Bitmask categories (e.g., audit success/failure in Security) | Essential in the Security log |
| `TimeCreated` | UTC timestamp with 100ns precision | Correlation backbone |
| `EventRecordID` | Monotonic per-log record counter | Detects log wrapping / gaps |
| `Correlation ActivityID` | GUID linking events of one operation | Gold for update/servicing chains |
| `Execution ProcessID/ThreadID` | Emitting process/thread | Ties events to a process |
| `Computer` / `Security UserID` | Machine and SID context | Attribution |

## Meaning
`Level` is the emitting developer's opinion, not ground truth — plenty of
Warning-level events are urgent (disk `153`) and some Errors are noise
(DCOM `10016`). Triage on *meaning*, using Level only as a first sort key.

## Related Entries
- V2.C1.E005 — Reading Event XML
- V2.C8.E10016 — DistributedCOM 10016 (the over-feared event)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — event schema — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V2.C1.E003
title: "Channels: System, Application, Security, Setup, and Applications & Services"
category: concept
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A **channel** is a named stream that events are published into and a log file
that persists them (`%SystemRoot%\System32\winevt\Logs\*.evtx`). The four
"Windows Logs" are the classic destinations; the Applications & Services tree
holds hundreds of component-specific channels, and much of the best diagnostic
signal now lives there.

## Meaning
| Channel | What lands here | Notes |
|---|---|---|
| System | Kernel, drivers, services (SCM), core OS components | First stop for boot/hardware/service issues |
| Application | User-mode application events: crashes (1000), WER (1001), MSI, .NET | First stop for app issues |
| Security | Audit records only; written exclusively by LSASS per audit policy | IDs here are effectively a stable Microsoft-controlled namespace |
| Setup | OS setup and servicing operations | Feature-update forensics |
| Applications & Services | Per-component Operational/Admin/Analytic/Debug channels | TaskScheduler, Defender, PowerShell, RDP, WLAN, Kernel-PnP, Diagnostics-Performance… |

Analytic and Debug channels are disabled by default and lossy by design —
enable them only for targeted captures, then disable.

## Diagnostic Procedure
1. List every channel and its size/record count:
```powershell
Get-WinEvent -ListLog * -ErrorAction SilentlyContinue |
  Sort-Object RecordCount -Descending |
  Select-Object LogName, RecordCount, FileSize, IsEnabled, LogMode
```
2. Export a channel for offline analysis:
```powershell
wevtutil epl Microsoft-Windows-TaskScheduler/Operational C:\Diag\tasksched.evtx
```

## Related Entries
- V2.C12.E001–E008 — the high-value Applications & Services channels

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — event log channels — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V2.C1.E004
title: "Enumerating Every Provider and ID on a Machine"
category: procedure
severity_for_triage: informational
applies_to: ["Windows 10", "Windows 11", "Windows Server 2016+"]
sources:
  - repo: "MicrosoftDocs/PowerShell-Docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Since no global event-ID catalog exists, the correct move is to generate the
catalog for *your* machine (or your fleet's reference image) directly from the
registered manifests. This procedure produces a complete, versioned CSV of
every event every installed provider can raise — typically 1,100+ providers
and 50,000+ distinct event definitions on a current Windows 11 client.

## Diagnostic Procedure
1. Count registered providers:
```powershell
(Get-WinEvent -ListProvider * -ErrorAction SilentlyContinue).Count
```
2. Dump one provider's full event table (IDs, versions, levels, templates):
```powershell
(Get-WinEvent -ListProvider 'Microsoft-Windows-Kernel-Power').Events |
  Select-Object Id, Version, Level, @{n='Description';e={$_.Description}} |
  Format-Table -Wrap
```
3. Build the machine-wide catalog (runs several minutes):
```powershell
$catalog = Get-WinEvent -ListProvider * -ErrorAction SilentlyContinue |
  ForEach-Object {
    $p = $_.Name
    $_.Events | ForEach-Object {
      [pscustomobject]@{
        Provider    = $p
        Id          = $_.Id
        Version     = $_.Version
        Level       = $_.Level.DisplayName
        Channel     = $_.LogLink.LogName
        Template    = ($_.Description -replace '\r?\n',' ')
      }
    }
  }
$catalog | Export-Csv C:\Diag\event-catalog.csv -NoTypeInformation -Encoding UTF8
```
4. Command-line equivalent for a single provider (shows the raw manifest view):
```cmd
wevtutil gp Microsoft-Windows-Kernel-Power /ge:true /gm:true
```
5. Some providers refuse metadata enumeration under a non-elevated token or
   return errors for legacy sources — that is why `SilentlyContinue` is used;
   log the failures rather than hiding them if completeness matters.

## Impact
This catalog is the ground truth that documentation approximates. Diffing
catalogs across OS builds reveals exactly which events Microsoft added,
removed, or re-versioned in an update.

## Related Entries
- V2.C1.E001 — The Provider-Manifest Model
- V7.C1.E001 — Get-WinEvent Mastery

## References & Attribution
- MicrosoftDocs/PowerShell-Docs — Get-WinEvent — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — catalog-generation procedure — License: n/a

---
entry_id: V2.C1.E005
title: "Reading Event XML: EventData, UserData, and Rendering"
category: concept
severity_for_triage: informational
applies_to: ["Windows Vista+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The "friendly" message in Event Viewer is a *rendering*: the stored event holds
raw values; the manifest's message template inserts them into localized text.
When automating, work from the XML, not the rendered string — strings vary by
language and template version; the XML fields do not.

## Meaning
- `<EventData>` — ordered `<Data>` elements, usually with `Name` attributes.
  Positional parsing breaks across event versions; parse by name when present.
- `<UserData>` — provider-defined custom XML schema (some components prefer it).
- If Event Viewer shows "The description for Event ID … cannot be found," the
  event is fine — the *manifest/message DLL* is missing on the viewing machine
  (common when opening `.evtx` files from another machine or after software
  removal). The raw data is still intact in the XML view.

## Diagnostic Procedure
1. Get an event as structured XML in PowerShell:
```powershell
$e = Get-WinEvent -FilterHashtable @{LogName='System'; Id=7000} -MaxEvents 1
([xml]$e.ToXml()).Event.EventData.Data | Select-Object Name, '#text'
```

## Related Entries
- V2.C1.E006 — XPath Filtering at Scale

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — event XML rendering — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V2.C1.E006
title: "Filtering at Scale: XPath Queries and Structured Filtering"
category: procedure
severity_for_triage: informational
applies_to: ["Windows 10", "Windows 11", "Windows Server 2016+"]
sources:
  - repo: "MicrosoftDocs/PowerShell-Docs"
    license: "CC BY 4.0 (adapted)"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Filtering server-side (in the event log service) is orders of magnitude faster
than pulling all events and filtering in PowerShell. Two mechanisms exist:
`-FilterHashtable` for common cases and XPath (`-FilterXPath` / `-FilterXml`)
for field-level precision. Windows XPath is a limited subset — no `contains()`
on all fields, positional and time functions are restricted.

## Diagnostic Procedure
1. Hashtable — errors in System in the last 24 hours:
```powershell
Get-WinEvent -FilterHashtable @{
  LogName   = 'System'
  Level     = 1,2
  StartTime = (Get-Date).AddDays(-1)
}
```
2. XPath — SCM 7000 for one specific service, by EventData field:
```powershell
Get-WinEvent -LogName System -FilterXPath `
  "*[System[EventID=7000]] and *[EventData[Data[@Name='param1']='Spooler']]"
```
3. Time windows in raw XPath use `timediff` (milliseconds relative to now):
```text
*[System[TimeCreated[timediff(@SystemTime) <= 86400000]]]
```
4. `-FilterXml` accepts the exact `<QueryList>` XML that Event Viewer's
   "Filter Current Log → XML tab" produces — build filters in the GUI, then
   paste them into automation.

## Related Entries
- V7.C1.E001 — Get-WinEvent Mastery

## References & Attribution
- MicrosoftDocs/PowerShell-Docs — Get-WinEvent filtering — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
