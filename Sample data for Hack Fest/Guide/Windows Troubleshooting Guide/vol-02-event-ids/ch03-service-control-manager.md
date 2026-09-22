# Volume II · Chapter 3 — System Log: Service Control Manager Events

All events in this chapter share: **Provider:** `Service Control Manager` ·
**Channel:** System. The SCM (`services.exe`) launches, monitors, and recovers
services; its 70xx series is the vocabulary of service failure.

---
entry_id: V2.C3.E7000
title: "SCM 7000: Service Failed to Start"
category: event-id
event: { id: 7000, provider: "Service Control Manager", channel: System, level: Error }
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
`7000` — "The <service> service failed to start due to the following error:
<error>" — is the SCM's generic start-failure record. The embedded Win32 error
is the entire diagnosis; the event without its error text is nearly useless.

## Message Text & Fields
| Field | Meaning |
|---|---|
| `param1` | Service display name |
| `param2` | Win32 error text (the rendered form of the error code) |

**Error-to-cause quick table (original synthesis):**
| Embedded error | Code | Dominant cause |
|---|---|---|
| The system cannot find the file specified | `2` | Binary path wrong/missing (uninstall leftovers, moved files) |
| Access is denied | `5` | Service account lacks rights on binary/keys, or EDR block |
| The service did not respond to the start or control request in a timely fashion | `1053` | Startup hang → see 7009; often .NET/dependency delay |
| The account name is invalid or does not exist, or the password is invalid | `1057`/`1069` | Broken service-account credentials |
| The service cannot be started… it is disabled | `1058` | Start type Disabled but something demanded a start |
| The dependency service or group failed to start | `1068` | Chase the dependency → 7001 |

## Likely Root Causes
1. Missing/invalid `ImagePath` after uninstall or AV quarantine. *very common*
2. Startup timeout (1053) from slow dependencies or profile issues. *very common*
3. Permissions: hardened folders, gMSA misconfig, EDR intervention. *common*
4. Stale logon credentials on "log on as" accounts after password change. *common*

## Diagnostic Procedure
1. Read the exact error:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Service Control Manager'; Id=7000} -MaxEvents 10 |
  Select-Object TimeCreated, Message | Format-List
```
2. Inspect the service definition:
```powershell
Get-CimInstance Win32_Service -Filter "Name='Spooler'" |
  Select-Object Name, State, StartMode, StartName, PathName
sc.exe qc Spooler
```
3. Verify the binary exists and the service account can read it:
```powershell
Test-Path (Get-CimInstance Win32_Service -Filter "Name='Spooler'").PathName.Trim('"').Split(' ')[0]
```
4. **[MODIFIES SYSTEM]** Attempt a manual start while watching for follow-on
   events:
```powershell
Start-Service Spooler -Verbose
```

## Resolution
Match the embedded error: restore/repair binary path (repair-install the app);
fix ACLs or EDR policy; for 1053 investigate the service's own logs and
consider the documented `ServicesPipeTimeout` registry adjustment only as a
diagnostic aid, not a fix; re-enter service credentials
(`services.msc` → Log On) after account password changes.

## Impact
A failed automatic service can silently disable printing, updates, security
agents, or line-of-business functions fleet-wide.

## Related Entries
- V2.C3.E7009 — start timeout detail
- V2.C3.E7001 — dependency chain failures

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — service start failures — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — error/cause table — License: n/a

---
entry_id: V2.C3.E7001
title: "SCM 7001: Dependency Service Failure"
category: event-id
event: { id: 7001, provider: "Service Control Manager", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`7001` — "The <service> service depends on the <dependency> service which
failed to start because of the following error…" — is a *pointer event*: the
named service is the victim; the dependency is the case to solve. Multiple 7001s
often cascade from one root 7000/7023.

## Diagnostic Procedure
1. Map the dependency tree of an affected service:
```powershell
Get-Service Netman -RequiredServices -ErrorAction SilentlyContinue
sc.exe enumdepend RpcSs 6000
```
2. Sort the burst of events by time; the *earliest* failing service in the
   chain is the root.

## Likely Root Causes
1. Root dependency failed (RPC, network stack, WMI). *very common*
2. Circular or broken dependency edits after software changes. *uncommon*

## Related Entries
- V2.C3.E7000 · V2.C3.E7023

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C3.E7009
title: "SCM 7009: Service Start Timeout"
category: event-id
event: { id: 7009, provider: "Service Control Manager", channel: System, level: Error }
severity_for_triage: medium
applies_to: ["all supported versions"]
sources: [{ repo: "MicrosoftDocs/SupportArticles-docs", license: "CC BY 4.0 (adapted)" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`7009` — "A timeout was reached (30000 milliseconds) while waiting for the
<service> service to connect" — means the process launched but never reported
`SERVICE_RUNNING` within the SCM's window (default 30 s). Usually followed by a
7000 with error 1053.

## Likely Root Causes
1. Slow initialization: cold .NET (NGEN not run), certificate revocation
   checks blocking on the network, database waits at boot. *very common*
2. Boot-storm contention on HDD-era or resource-starved machines/VMs. *common*
3. Service bug: main thread deadlock before signaling. *common*

## Diagnostic Procedure
1. Confirm the pattern (7009 + 7000/1053 pairs) and whether it is boot-only:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=7009,7000} -MaxEvents 30 |
  Select-Object TimeCreated, Id, Message
```
2. Time a manual start after boot has settled — success then indicates
   boot-time contention, not a broken service.
3. For network-dependent services, test with CRL endpoints reachable vs. not
   (offline revocation stalls are a classic hidden cause).
4. **[MODIFIES SYSTEM]** Delayed start is often the correct fix:
```powershell
sc.exe config MyService start= delayed-auto
```

## Resolution
Prefer delayed-auto start or fixing the slow dependency. Raising
`HKLM\SYSTEM\CurrentControlSet\Control\ServicesPipeTimeout` masks the symptom
and delays boot diagnostics — use only when the vendor requires it.

## Related Entries
- V2.C3.E7000 · V2.C3.E7011

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — 7000/7009/7011 timeout guidance — License: CC BY 4.0 (adapted) — retrieved 2026-08-30

---
entry_id: V2.C3.E7011
title: "SCM 7011: Transaction Response Timeout"
category: event-id
event: { id: 7011, provider: "Service Control Manager", channel: System, level: Error }
severity_for_triage: medium
applies_to: ["all supported versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`7011` — "A timeout (30000 milliseconds) was reached while waiting for a
transaction response from the <service> service" — is a *runtime* control
timeout: a running service failed to answer an SCM control (stop, shutdown,
session change) in time. Bursts of 7011 during shutdown are the signature of
"this machine takes forever to restart."

## Likely Root Causes
1. Service hung on stop (flushing, waiting on network/DB). *very common*
2. Shared-process (svchost) sibling blocking the control pipe. *common*
3. Deadlocked session-change handling (fast user switching/RDP). *uncommon*

## Diagnostic Procedure
1. Identify repeat offenders and whether events cluster at shutdown times:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=7011} -MaxEvents 50 |
  Group-Object { ($_ .Message -split "'")[1] } | Sort-Object Count -Descending
```
2. Capture a hang dump of the offender during a stop attempt (Task Manager →
   Create dump, or ProcDump) and inspect thread stacks (`V3.C2.E003`).

## Related Entries
- V2.C3.E7009 · V2.C7.E1002 (Application Hang)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C3.E7023
title: "SCM 7023: Service Terminated with Error"
category: event-id
event: { id: 7023, provider: "Service Control Manager", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`7023` — "The <service> service terminated with the following error: <error>"
— means the service started, ran, and then *exited deliberately*, reporting a
Win32 error as its exit status. Unlike 7031/7034 (crash), 7023 is the service
saying "I chose to stop, and here's why."

## Meaning
The embedded error is the service's own verdict: `Access is denied`,
`The specified module could not be found`, `Not enough storage`, endpoint/port
conflicts, and similar. Interpret it in the service's own domain — the same
code means different things for DNS Client vs. a vendor agent.

## Likely Root Causes
1. Configuration invalid at runtime (port in use, path revoked, quota). *common*
2. Dependency vanished mid-run (dismounted volume, revoked credentials). *common*
3. Missing DLL after a partial update (error 126). *common*

## Diagnostic Procedure
1. Read the error and check the service's own Operational channel or logs.
2. Cross-check Application log for the same service name in ±1 minute.
3. Reproduce with the service running in console/debug mode if the vendor
   supports it — 7023 causes are usually loggable by the service itself.

## Related Entries
- V2.C3.E7031 — crash-based termination (contrast)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C3.E7031
title: "SCM 7031/7034: Service Crash and Recovery Action"
category: event-id
event: { id: 7031, provider: "Service Control Manager", channel: System, level: Error }
severity_for_triage: high
applies_to: ["all supported versions"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Both record *unexpected* service termination — the process died without telling
the SCM. `7031` is written when recovery actions are configured (and names the
action about to run: "Restart the service in 60000 milliseconds"); `7034` is
written when no recovery is configured. Either way: the service crashed, and
the real evidence is in the Application log.

## Meaning
7031/7034 carry no cause. The cause lives in the paired Application-log records:
Application Error `1000` (native crash), .NET Runtime `1026` (managed
exception), and WER `1001` (bucket + dump pointer) for the same PID/time.

## Likely Root Causes
1. Unhandled exception in the service (see the paired 1000/1026). *very common*
2. Killed externally (EDR, admin taskkill, OOM). *common*
3. Heap/handle exhaustion over long uptimes — crash after days/weeks. *common*

## Diagnostic Procedure
1. Find the crash pair:
```powershell
$t = (Get-WinEvent -FilterHashtable @{LogName='System'; Id=7031,7034} -MaxEvents 1).TimeCreated
Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=$t.AddMinutes(-2); EndTime=$t.AddMinutes(1)} |
  Where-Object Id -in 1000,1001,1002,1026 | Format-List TimeCreated, Id, Message
```
2. **[MODIFIES SYSTEM]** Enable LocalDumps for the service executable to catch
   the next occurrence (`V3.C1.E007`), then analyze per `V3.C2.E003`.
3. Review recovery settings so a crash-looping service doesn't mask frequency:
```cmd
sc.exe qfailure MyService
```

## Impact
Crash-looping services under aggressive recovery can hammer dependencies and
hide instability; 7034 without recovery leaves functions silently down.

## Related Entries
- V2.C7.E1000 — Application Error 1000
- V3.C1.E002 — Report.wer anatomy

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C3.E7045
title: "SCM 7045: New Service Installed (Security-Relevant)"
category: event-id
event: { id: 7045, provider: "Service Control Manager", channel: System, level: Information }
severity_for_triage: medium
applies_to: ["Windows 7+ / Server 2008 R2+"]
sources:
  - repo: "MicrosoftDocs/windows-itpro-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`7045` — "A service was installed in the system" — records service name, image
path, service type, start type, and installing account. Operationally mundane;
forensically precious: service installation is a classic persistence and
lateral-movement technique (remote-exec tools install temporary services), so
7045 review is standard in incident response.

## Message Text & Fields
| Field | Watch for |
|---|---|
| Service File Name | Paths in `%TEMP%`, user profiles, UNC paths; `cmd /c`, `powershell -enc` in the image path |
| Service Name | Random-looking names; known admin-tool patterns |
| Account | Unexpected user contexts |
| Start Type | `demand start` created then removed = one-shot execution |

## Diagnostic Procedure
1. Audit recent installs:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Service Control Manager'; Id=7045} -MaxEvents 50 |
  Select-Object TimeCreated, Message | Format-List
```
2. Correlate with Security `4697` (the audited counterpart, richer subject
   data) where Advanced Audit Policy enables it.

## Related Entries
- V2.C11.E4697 — Security 4697
- V2.C12.E003 — PowerShell script block logging

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — security auditing guidance — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — hunting heuristics — License: n/a
