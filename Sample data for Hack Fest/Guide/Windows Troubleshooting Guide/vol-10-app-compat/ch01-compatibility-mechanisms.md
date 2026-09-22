# Volume X · Chapter 1 — Compatibility Mechanisms

Why old apps break on new Windows, and the machinery that makes them work
anyway. Most "compatibility" tickets are actually one of three things: a
missing shim, a UAC/virtualization mismatch, or a per-user vs. per-machine
install problem — each with a clean diagnostic.

---
entry_id: V10.C1.E001
title: "Shims and the Application Compatibility Toolkit"
category: concept
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A **shim** is a small compatibility fix Windows inserts between an application
and the OS — intercepting API calls to lie helpfully (report an older OS
version, redirect a path, relax a security check) so a legacy app runs
unmodified. Windows ships thousands of shims applied automatically; the
**Application Compatibility Toolkit** (ACT, now part of the ADK) lets admins
author and deploy custom shim databases (`.sdb`) for in-house apps.

## Meaning
Common built-in shims: version-lie (`WinXPSp3VersionLie` and successors),
`RunAsInvoker` (skip a bogus elevation prompt), path/registry redirection.
When an app works after setting Compatibility-tab options, that's a shim being
applied — the tab is a friendly front end to the shim engine. For fleet
deployment, a custom `.sdb` applied via `sdbinst.exe` fixes an app everywhere
without touching the app.

The troubleshooting flip side: shims are invisible unless you look. An app that
mysteriously works on one machine and not another may have a shim database
installed on one; `sdbinst` inventory reveals it.

## Diagnostic Procedure
1. See installed custom shim databases:
```powershell
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\InstalledSDB' -EA SilentlyContinue |
  ForEach-Object { Get-ItemProperty $_.PSPath } | Select-Object DatabaseDescription, DatabasePath
```
2. Per-app compatibility settings a user/admin set (the Compatibility tab
   writes here):
```powershell
Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers' -EA SilentlyContinue
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers' -EA SilentlyContinue
```
3. Author/deploy a fix with the Compatibility Administrator (ACT) → produce
   `.sdb` → deploy: `sdbinst.exe fix.sdb` (`sdbinst -u` to remove).
4. Note: shims run in user mode and don't fix kernel-mode issues (drivers) or
   genuinely incompatible code — they buy time, not permanence.

## Related Entries
- V10.C1.E002 — UAC/virtualization (a related compat mechanism) · V10.C2.E003 — LOB apps

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Application Compatibility Toolkit / shims — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — invisible-shim note — License: n/a

---
entry_id: V10.C1.E002
title: "UAC, Virtualization, and Per-User vs. Per-Machine Installs"
category: concept
severity_for_triage: medium
applies_to: ["Windows Vista+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Legacy apps that write to protected locations (`C:\Program Files`,
`HKLM\SOFTWARE`) without admin rights are silently redirected by **UAC
virtualization** to per-user shadow locations (`%LOCALAPPDATA%\VirtualStore`
and `HKCU\...\Classes\VirtualStore`). This keeps them running but produces the
baffling "my settings don't apply for other users" / "the change vanished"
symptom — the app is reading/writing its own private virtualized copy.

## Meaning
- **Virtualization only applies to 32-bit apps without a requested execution
  level** and only for the legacy locations; modern/manifested apps are not
  virtualized (they just get access-denied instead, which is at least honest).
- **Per-user vs. per-machine installs**: an app installed "just for me" lives
  in the profile and is invisible to other users; deployed software should be
  per-machine. "It works for the user who installed it but nobody else" is the
  signature.
- The fix is rarely "disable UAC" (a security regression) — it's manifesting
  the app correctly, using proper per-user data locations, or a redirection
  shim (E001).

## Diagnostic Procedure
1. Check the VirtualStore when settings mysteriously don't persist/share:
```powershell
Get-ChildItem "$env:LOCALAPPDATA\VirtualStore" -Recurse -EA SilentlyContinue |
  Select-Object FullName
reg query "HKCU\SOFTWARE\Classes\VirtualStore" 2>$null
```
2. Determine an app's requested execution level (manifested apps aren't
   virtualized): inspect the executable's manifest (Sysinternals `sigcheck -m`)
   for `requestedExecutionLevel`.
3. Per-user vs. per-machine: check both uninstall hives
   (`HKLM\...\Uninstall`, `HKLM\WOW6432Node\...\Uninstall`, and
   `HKCU\...\Uninstall`) — a product only in HKCU is a per-user install.

## Related Entries
- V1.C2.E004 — registry virtualization · V10.C1.E003 — the access-denied cases

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — UAC / virtualization — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — signature symptoms — License: n/a

---
entry_id: V10.C1.E003
title: "Diagnosing 'Works for Admin, Not for User' and DLL/Runtime Issues"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Two of the most common app-support tickets: an app that runs elevated but fails
as a standard user (a permissions/registry-access problem), and an app that
won't launch at all (a missing runtime/DLL). Both are solved fast with the
right tool — Process Monitor for the first, dependency inspection for the
second — instead of reinstall-roulette.

## Diagnostic Procedure
1. **"Works for admin, not for user"** — capture what the app is denied:
```
Process Monitor (V1.C3.E005):
  Filter: Process Name is <app.exe>
  Filter: Result is not SUCCESS
  Run as the standard user, reproduce, and read the ACCESS DENIED /
  NAME NOT FOUND lines — they name the exact file or registry key the user
  lacks rights to. That path IS the fix (grant access, relocate the data,
  or shim the redirection).
```
   The dominant causes: the app writing to `HKLM`/`Program Files` at runtime
   (virtualization E002, or genuinely broken as a standard user) and
   hard-coded paths.
2. **"Won't launch — missing DLL/runtime"** — decode the loader error first
   (V3.C1.E006 codes: `0xC0000135` DLL not found, `0xC0000139` entry point,
   `0xC000007B` bad image / bitness mismatch), then inspect dependencies:
```powershell
# what the process tried to load (from the crash) — check the WER report's
# LoadedModule list (V3.C1.E002), or statically:
# use dumpbin /dependents or Dependencies (the modern Dependency Walker) on app.exe
```
   The usual fix: install the matching **Visual C++ Redistributable** (the
   single most common missing runtime), the correct **.NET** version, or
   resolve a 32/64-bit mismatch (`0xC000007B` is almost always bitness).
3. **Confirm the fix per user context** — always retest as the *affected*
   account, not as admin; "fixed for me" (admin) is the classic false positive.

## Related Entries
- V1.C3.E005 — Process Monitor · V3.C1.E006 — loader error codes · V10.C1.E002 — virtualization

## References & Attribution
- original synthesis — License: n/a
