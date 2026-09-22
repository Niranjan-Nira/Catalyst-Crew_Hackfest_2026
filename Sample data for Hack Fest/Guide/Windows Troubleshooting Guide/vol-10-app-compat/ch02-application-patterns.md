# Volume X · Chapter 2 — Application Patterns

The three application families that generate the most tickets — Office,
browsers, and line-of-business apps — each have a repeatable triage pattern.
Learn the pattern once; apply it to every instance.

---
entry_id: V10.C2.E001
title: "Office Troubleshooting (Safe Mode, Add-ins, Repair)"
category: procedure
severity_for_triage: medium
applies_to: ["Microsoft 365 Apps / Office 2016+"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The overwhelming majority of Office crashes, hangs, and "won't start" problems
are caused by **add-ins** — COM add-ins, VSTO plugins, and vendor toolbars
injecting into the Office process (they appear as the third-party module in the
1000/1002 events of V2.C7). The triage is a fixed sequence: safe mode →
disable add-ins → repair → profile.

## Diagnostic Procedure
1. **Safe mode isolates add-ins** (loads Office with add-ins and customizations
   off):
```cmd
excel.exe /safe
outlook.exe /safe
```
   Works in safe mode, fails normally = an add-in or customization. This one
   test resolves the majority of cases' *direction*.
2. **Bisect add-ins** — File → Options → Add-ins → Manage (COM Add-ins) → Go;
   disable all, re-enable one at a time. Or read what's loaded:
```powershell
Get-ChildItem 'HKCU:\SOFTWARE\Microsoft\Office\Excel\Addins',
              'HKLM:\SOFTWARE\Microsoft\Office\Excel\Addins' -EA SilentlyContinue |
  ForEach-Object { Get-ItemProperty $_.PSPath } |
  Select-Object PSChildName, LoadBehavior, FriendlyName
```
   (`LoadBehavior 3` = load at startup; set to `2` to disable.)
3. **Correlate with crash events** — the faulting module in Application Error
   1000 (V2.C7.E1000) frequently names the culprit add-in DLL directly.
4. **Repair** — Online Repair (Control Panel → Programs → Microsoft 365 →
   Change → Online Repair) rebuilds a corrupted install; Quick Repair first
   (faster, no download).
5. **Outlook specifics** — profile corruption is a distinct cause: test with a
   new mail profile (Control Panel → Mail → Show Profiles), and for OST/data
   issues, `scanpst.exe`. Cached-mode vs. online changes the failure surface.
6. **New profile test** — a fresh Windows user profile isolates
   Office-config-vs-machine issues.

## Related Entries
- V2.C7.E1000/E1002 — the crash/hang events naming the add-in

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — Office troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — triage sequence — License: n/a

---
entry_id: V10.C2.E002
title: "Browser and Edge/WebView2 Patterns"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Browser tickets cluster into a small set: extensions breaking pages, policy/
profile corruption, network/TLS problems that *look* like browser bugs (really
Chapter 8 issues), and — increasingly — **WebView2** problems, since many
desktop apps now embed Edge/WebView2 and inherit its failures. The pattern
mirrors Office: isolate with a clean profile / no extensions, then localize.

## Diagnostic Procedure
1. **Isolate profile + extensions** (clean-session test):
```cmd
msedge.exe --inprivate            :: extensions off, fresh session
msedge.exe --user-data-dir=%TEMP%\edgetest   :: throwaway profile
```
   Works clean = a profile or extension problem; bisect extensions.
2. **Enterprise policy** — managed browsers get policies that break sites or
   features; read effective policy:
```
edge://policy    (and chrome://policy)  — shows applied policies and conflicts
```
3. **"Only this site fails" / cert errors** = network/TLS, not the browser —
   go to Volume VIII (proxy V8.C3.E001, TLS inspection V8.C3.E003, DNS
   Chapter 1). The browser is the messenger.
4. **WebView2 in a desktop app** — the app embeds Edge; failures show as the
   app's own crash but trace to the WebView2 Runtime:
```powershell
# Is the Evergreen WebView2 Runtime installed / current?
Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -EA SilentlyContinue |
  Select-Object pv, name
```
   Missing/outdated WebView2 Runtime is a common "the app's screen is blank/
   broken" cause; reinstall the Evergreen runtime.

## Related Entries
- V8.C3.E001/E003 — proxy & TLS · V8.C1.* — DNS · V2.C7.E1000 — embedded-browser crashes

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V10.C2.E003
title: "Line-of-Business App Deployment and Failure Triage"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11 enterprise"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Custom and vendor line-of-business apps are the hardest to support (no public
knowledge base) but they fail in the *same* documented ways everything else
does — so the encyclopedia's whole toolkit applies. This entry is the
integrating checklist that routes an LOB failure to the right chapter.

## Diagnostic Procedure
The LOB triage routing table — match the symptom, go to the entry:
| Symptom | Route to |
|---|---|
| Won't install (MSI) | V2.C8.E11707 (verbose log, return value 3) |
| Won't install (managed: Intune/ConfigMgr) | V5.C2.E002 (CSP/report) + the deployment tool's own log |
| Won't launch — missing DLL/runtime | V10.C1.E003 + V3.C1.E006 (loader codes) |
| Crashes | V2.C7.E1000/E1026 → dump V3.C2.E003 |
| Hangs | V2.C7.E1002 → hang dump / wait chain |
| Works for admin only | V10.C1.E003 (ProcMon ACCESS DENIED) |
| Settings don't persist/share | V10.C1.E002 (UAC virtualization) |
| Service won't start | V2.C3.E7000 family |
| Network/API failures | V8.* (proxy, DNS, TLS, ports) |
| Slow | V9.* (CPU/memory/disk attribution) |
| Certificate/auth errors | V2.C12.E008 (CAPI2) + V8.C3.E003 |
| Database (embedded ESE) errors | V2.C8.E455 |

## Meaning — the LOB-specific additions
1. **Get the vendor a real artifact, not a description**: a dump (V3.C2), a
   ProcMon capture filtered to the failure, or the exact event with codes —
   turns "it doesn't work" into an actionable report.
2. **Reproduce in a clean context**: new user profile + clean machine isolates
   app-vs-environment; if it fails clean, it's the app/deployment, not the
   fleet.
3. **Version and dependency pinning**: LOB apps often require a specific
   VC++/.NET/Java/driver version — capture the working vs. broken machine's
   dependency versions and diff (the "what changed" method, V1.C1.E003).
4. **Own the packaging**: many LOB failures are packaging defects (wrong
   install context, missing prereqs in the package, hard-coded paths) — fixable
   with a shim (V10.C1.E001) or repackaging, without vendor involvement.

## Related Entries
- Effectively the whole encyclopedia — this is the integrating entry
- V1.C1.E001 — the disciplined method that ties it together

## References & Attribution
- original synthesis — License: n/a
