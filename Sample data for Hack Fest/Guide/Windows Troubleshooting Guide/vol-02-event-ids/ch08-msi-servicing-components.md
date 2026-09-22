# Volume II · Chapter 8 — Application Log: MSI, Servicing, and Component Events

The Application log's second population (after crashes): installers, user
profiles, COM activation noise, and the database engine half of Windows runs
on. Includes the most over-feared event in Windows and the most misread ones.

---
entry_id: V2.C8.E11707
title: "MsiInstaller 11707/11708/1033/1034: Install Success and Failure"
category: event-id
event: { id: 11708, provider: "MsiInstaller", channel: Application, level: Information }
severity_for_triage: medium
applies_to: ["all supported versions"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Windows Installer's ledger: `11707` — "Product: <X> — Installation completed
successfully"; `11708` — "…Installation failed"; `11724` — removal succeeded;
`1033/1034` — install/removal transaction records carrying **the numeric
result** (0 success, `1603` fatal error, `1618` another install in progress,
`1619/1620` package unreadable, `1638` another version installed, `3010`
success-needs-reboot); `1040/1042` — transaction start/end (with the client
process — *who* launched the install). The event says pass/fail; the **why**
of a 1603 lives only in verbose MSI logs.

## Meaning
`1603` is a container, not a cause. The standard extraction: get a verbose log
and search upward from the first `return value 3` — the custom action or
standard action just above it is the failure; its surrounding lines carry the
real error (file in use, permission, missing prerequisite, custom-action
script exception). `1618` = serialize your deployments (msiexec mutex);
`1638` = upgrade logic problem, not corruption.

## Diagnostic Procedure
1. Install history with results:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='MsiInstaller'; Id=11707,11708,1033,1034} -MaxEvents 30 |
  Select-Object TimeCreated, Id, Message
```
2. Reproduce with verbose logging (the diagnostic gold standard):
```cmd
msiexec /i package.msi /L*v C:\Diag\install.log
```
3. In the log: find `return value 3`, read upward. Managed deployments
   (Intune/ConfigMgr) keep their own logs wrapping the MSI result — correlate
   by time.
4. Machine-wide policy logging when you can't rerun interactively:
   `HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer` → `Logging=voicewarmupx`
   writes `%TEMP%\MSI*.log` for every transaction. **[MODIFIES SYSTEM]**

## Related Entries
- V2.C3.E7045 — services installed by packages · V4.C2 — servicing analogs

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C8.E1530
title: "User Profile Service 1530/1533/1511/1508: Profile Load Failures"
category: event-id
event: { id: 1511, provider: "Microsoft-Windows-User Profiles Service", channel: Application, level: Warning }
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
The profile service narrates every logon's profile work. The IDs that matter:
`1511` — "Windows cannot find the local profile and is logging you on with a
**temporary** profile" (the TEMP-profile logon users report as "all my files
are gone"); `1508/1500` — registry hive load failed (with the error);
`1530` — "Windows detected your registry file is still in use by other
applications or services" (lists the **leaked handles and their owners** —
read them, they name the culprit); `1533` — cannot delete profile directory;
`1542` — hive corruption on load.

## Meaning
The TEMP-profile mechanism: when the NTUSER.DAT hive can't load (corrupt,
locked, missing) or the profile path is inaccessible, Windows logs 1511 and
builds a throwaway profile; simultaneously the ProfileList registry key for
the user's SID gets renamed with a `.bak` suffix. Nothing is lost — the real
profile folder still exists — but every logon lands in TEMP until the
ProfileList state and the underlying cause are repaired. 1530 is different:
it fires at *logoff*, and its handle list (services/AV holding NTUSER.DAT
open) explains slow logoffs and "registry in use" — chronic 1530 from the
same product is a vendor bug report waiting to be filed.

## Likely Root Causes
1. **NTUSER.DAT corruption** — unclean shutdowns, disk issues (pair with
   V2.C4). *common*
2. **ProfileList `.bak` state** left by a prior failure. *very common as the
   persisting mechanism*
3. **Permissions/ownership damage** on the profile folder. *common*
4. **Profile-holding software** (AV, backup, virtualization agents) locking
   the hive at the wrong moment. *common*

## Diagnostic Procedure
1. Read the event pair (1511 + the 1508/1542 that preceded it) for the stated
   reason.
2. Inspect ProfileList for the user's SID:
```powershell
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' |
  Where-Object Name -match '\.bak$|S-1-5-21' |
  Get-ItemProperty | Select-Object PSChildName, ProfileImagePath, State
```
3. **[MODIFIES SYSTEM]** Standard repair: log the user off, remove the
   *duplicate* non-`.bak` SID key created for the TEMP profile, rename the
   `.bak` key back (remove suffix), set its `State` to 0, verify
   NTUSER.DAT loads (`reg load HKU\Test <path>\NTUSER.DAT` then `reg unload
   HKU\Test`), and have the user log on. Hive won't load = restore NTUSER.DAT
   from backup/previous versions.
4. For 1530 slow-logoff complaints: read the handle owners in the event and
   pursue the named product.

## Impact
TEMP-profile logons look like data loss to users and generate panic tickets;
the repair is routine once the ProfileList mechanism is understood.

## Related Entries
- V1.C2.E004 — hive mechanics · V2.C4.E055 — upstream corruption

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — temporary profile troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — repair sequence framing — License: n/a

---
entry_id: V2.C8.E10016
title: "DistributedCOM 10016: The Most Over-Feared Event in Windows"
category: event-id
event: { id: 10016, provider: "Microsoft-Windows-DistributedCOM", channel: System, level: Error }
severity_for_triage: low
applies_to: ["Windows 10/11, Server 2016+"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`10016` — "The application-specific permission settings do not grant Local
Activation permission for the COM Server application with CLSID {…} and APPID
{…} to the user <X> from address LocalHost…" — is an Error-level event that
is, in the overwhelming majority of occurrences, **by-design noise**:
Windows components requesting COM activation with permissions they don't
have and don't need, falling back gracefully. Microsoft's own guidance says
these specific system-generated 10016s can be ignored and are protected by
TrustedInstaller ownership precisely so admins don't "fix" them.

## Meaning
When it *does* matter: a third-party application actually failing, with a
10016 whose CLSID/AppID resolves to that application's COM server and whose
timestamp matches the failure. The test is functional: no failing
application = no action. The internet's standard remedy — taking ownership of
the registry keys and editing DCOM ACLs — modifies protected OS configuration
to silence a cosmetic event, and creates real support debt.

## Diagnostic Procedure
1. Resolve the CLSID/AppID to a name before judging:
```powershell
$clsid = '{D63B10C5-BB46-4990-A94F-E40B9D520160}'
(Get-ItemProperty "Registry::HKCR\CLSID\$clsid" -ErrorAction SilentlyContinue).'(default)'
```
2. Decide: OS component (RuntimeBroker, per-user services, shell classes) →
   ignore/filter; matches a failing app → grant that specific principal the
   specific activation right via Component Services on the *application's*
   AppID (a supported, targeted change).
3. If the noise bothers monitoring, filter the specific CLSID/AppID pairs in
   the SIEM/collector query — not the registry.

## Impact
Zero, in the noise case — the entry exists to save the hours spent "fixing"
it and to keep protected ACLs intact.

## Related Entries
- V1.C2.E007 — COM/DCOM mechanics · V2.C1.E002 — Level ≠ importance

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — DCOM 10016 guidance — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — decision test — License: n/a

---
entry_id: V2.C8.E455
title: "ESENT 455/489/490/623: Database Engine File Errors"
category: event-id
event: { id: 455, provider: "ESENT", channel: Application, level: Error }
severity_for_triage: medium
applies_to: ["all supported versions"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
ESENT (the Extensible Storage Engine) is the embedded database under much of
Windows: search index, WU datastore, certificate stores, WebCache, and many
apps. Its Application-log errors name the **client and file**: `455` — error
opening a **log file** (path in the event; `-1023` invalid path, `-1811` file
not found); `489/490` — read-only/attach failures on a database file; `623` —
version-store exhaustion (a *transaction* problem, not corruption); `508/510`
— slow I/O warnings (ESENT complaining about the disk — treat as a
storage-latency signal, pair with V2.C4).

## Meaning
Triage by the *path* in the event, which names the owning component:
`...\SoftwareDistribution\DataStore` → WU datastore (repair = the reset
procedure, V4.C2.E006); `...\Windows\system32\config\systemprofile\...\WebCache`
→ WebCache/WinHTTP per-profile database; search index paths → rebuild the
index. A famous benign pattern: 455s referencing a missing `TileDataLayer`
or per-profile path shortly after profile changes — a component looking for
a database that legitimately no longer exists. Rising 508/510 volume across
*different* databases is not an ESENT problem at all — it's the disk (latency
counters, V1.C3.E003).

## Diagnostic Procedure
1. Group by database path to find the owning component:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='ESENT'; Level=2,3} -MaxEvents 100 |
  Group-Object { if ($_.Message -match '([A-Za-z]:\\[^\s"]+)') { $Matches[1] } else { 'n/a' } } |
  Sort-Object Count -Descending | Select-Object Count, Name -First 10
```
2. Component-appropriate repair: WU datastore → V4.C2.E006; search →
   Indexing Options → Rebuild; app databases → the app's own maintenance
   (many ESENT clients self-heal by rebuilding on next start after the stale
   files are cleared with the service stopped).
3. `esentutl` exists (`/g` integrity, `/p` repair) — use only on databases
   whose owning service is stopped, and only when the component offers no
   rebuild path; `/p` is lossy by design.

## Related Entries
- V4.C2.E006 — WU datastore reset · V2.C4 — when ESENT is the storage canary

## References & Attribution
- original synthesis — License: n/a
