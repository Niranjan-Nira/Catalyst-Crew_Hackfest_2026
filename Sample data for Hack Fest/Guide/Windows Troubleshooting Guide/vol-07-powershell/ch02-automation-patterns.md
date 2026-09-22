# Volume VII · Chapter 2 — Automation Patterns

Moving from interactive cmdlets to a collector that runs unattended, on any
enterprise machine, and tells the truth about what it couldn't gather. These
are the patterns behind V1.C3.E009's design principles.

---
entry_id: V7.C2.E001
title: "Background Jobs vs. Runspaces for Concurrent Collection"
category: concept
severity_for_triage: informational
applies_to: ["Windows PowerShell 5.1 / PowerShell 7"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Diagnostic collection has a concurrency problem: static snapshots are quick,
but a live monitor (sampling counters/events over, say, 30 minutes) must run
*alongside* everything else, not block it. Two mechanisms exist, with a real
tradeoff.

## Meaning
| Mechanism | Nature | Use when |
|---|---|---|
| `Start-Job` (background jobs) | Each job is a separate `pwsh`/`powershell` **process** — heavy startup, full isolation, survives independently | A few long-running parallel tasks (the 30-minute live monitor beside static collection); simplicity matters more than overhead |
| Runspaces / `ForEach-Object -Parallel` (PS7) | Threads in one process — light, fast, shared session state | Many short parallel tasks (querying 500 machines, hashing many files) where per-task process overhead would dominate |
| `Invoke-Command` (remoting) | Runs on *other* machines in parallel | Fleet collection across hosts |

For a single-machine collector, the common shape is: kick off the live
monitor as one background job, run static modules in the foreground, then
`Receive-Job` the monitor at the end. This is the "phase separation" principle
of V1.C3.E009 in code — don't serialize a half-hour monitor behind
point-in-time collection.

## Diagnostic Procedure
```powershell
# Start the 30-min live monitor without blocking static collection
$monitor = Start-Job -Name LiveMon -ScriptBlock {
  param($minutes)
  $end = (Get-Date).AddMinutes($minutes)
  while ((Get-Date) -lt $end) {
    [pscustomobject]@{
      Time = Get-Date
      CPU  = (Get-CimInstance Win32_Processor).LoadPercentage
      FreeMB = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)
    }
    Start-Sleep -Seconds 30
  }
} -ArgumentList 30

# ... run static collection modules here in the foreground ...

$samples = Receive-Job $monitor -Wait -AutoRemoveJob
```

## Related Entries
- V1.C3.E009 — collector design · V7.C2.E003 — packaging

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V7.C2.E002
title: "Robust Error Handling and Transcript Logging"
category: procedure
severity_for_triage: informational
applies_to: ["Windows PowerShell 5.1 / PowerShell 7"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A diagnostic script that fails silently is worse than none — it produces a
package that *looks* complete and isn't. The discipline: make every collection
attempt report its outcome, distinguish "not applicable" from "failed," and
capture enough to explain a failure without re-running.

## Diagnostic Procedure
1. **Terminating vs. non-terminating:** many cmdlets emit non-terminating
   errors that `try/catch` won't catch unless you force them:
```powershell
try {
  $dumps = Get-ChildItem C:\Windows\Minidump -ErrorAction Stop
  $status = 'OK'
} catch [System.Management.Automation.ItemNotFoundException] {
  $status = 'NONE'      # legitimately absent — not a failure
} catch {
  $status = "FAIL: $($_.Exception.Message)"
}
```
   `-ErrorAction Stop` turns non-terminating errors into catchable exceptions;
   catch specific types to separate "empty" from "broken."
2. **Record the reason, classified:** access-denied, policy-blocked, and
   feature-absent are different stories — a good status log says which:
```powershell
# Detecting a policy block (e.g. WER disabled) is itself a finding
$werDisabled = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting' -EA SilentlyContinue).Disabled
if ($werDisabled) { $status = 'BLOCKED: WER disabled by policy' }
```
3. **Transcript for the whole run:**
```powershell
Start-Transcript -Path "$run\transcript.log" -Append
# ... work ...
Stop-Transcript
```
4. **Honest hardware claims:** when a metric isn't available through standard
   APIs (CPU temperature, fan RPM, PSU rail voltage), write `unavailable` with
   the reason — never emit a plausible zero that a reader will trust.

## Impact
The difference between a collector that helps and one that misleads is almost
entirely in this entry: explicit, classified failure visibility.

## Related Entries
- V1.C1.E004 — first-response kit · V1.C3.E009 — collector principles

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V7.C2.E003
title: "Packaging Diagnostic Output (Compress-Archive, Status Manifests)"
category: procedure
severity_for_triage: informational
applies_to: ["Windows PowerShell 5.1 / PowerShell 7"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The package is the product. A good diagnostic bundle is self-describing: a
deterministic layout, a manifest saying what ran and what it found, hashes for
integrity, and a single archive a human or pipeline can consume.

## Diagnostic Procedure
1. Deterministic run directory + manifest:
```powershell
$run = Join-Path 'C:\Diag' ("{0}_{1:yyyyMMdd-HHmmss}" -f $env:COMPUTERNAME, (Get-Date))
New-Item $run -ItemType Directory -Force | Out-Null

$manifest = [ordered]@{
  Computer   = $env:COMPUTERNAME
  Collected  = (Get-Date).ToString('o')
  OSBuild    = (Get-CimInstance Win32_OperatingSystem).BuildNumber
  PSVersion  = $PSVersionTable.PSVersion.ToString()
  RunAs      = "$env:USERDOMAIN\$env:USERNAME"
  Modules    = @()   # filled per module with Result/Duration
}
```
2. Hash collected files for integrity:
```powershell
Get-ChildItem $run -Recurse -File |
  Get-FileHash -Algorithm SHA256 |
  Select-Object Hash, Path | Export-Csv "$run\hashes.csv" -NoTypeInformation
```
3. Write the manifest and archive:
```powershell
$manifest | ConvertTo-Json -Depth 5 | Set-Content "$run\manifest.json"
Compress-Archive -Path "$run\*" -DestinationPath "$run.zip" -CompressionLevel Optimal
```
4. Size discipline: exported `.evtx` and dumps dominate size — cap or
   selectively include (last N days of events, minidumps not full MEMORY.DMP
   unless requested), and note in the manifest what was truncated.
5. `Compress-Archive` has historically struggled with very large sets and
   locked files; for big packages, collect to a staging folder first (copy,
   don't archive open files) and archive the copies.

## Related Entries
- V7.C2.E002 — the status data that feeds the manifest · V1.C3.E009

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V7.C2.E004
title: "Remoting: WinRM Configuration and Troubleshooting"
category: procedure
severity_for_triage: medium
applies_to: ["Windows PowerShell 5.1 / PowerShell 7"]
sources:
  - repo: "MicrosoftDocs/PowerShell-Docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Fleet diagnostics need remoting, and remoting fails in predictable ways.
PowerShell remoting runs over WinRM (WS-Management, HTTP 5985 / HTTPS 5986) —
a different transport from the CIM/DCOM path, with its own enablement, auth,
and firewall requirements. The common failures all have specific causes.

## Diagnostic Procedure
1. Test the actual channel before blaming PowerShell:
```powershell
Test-NetConnection SERVER01 -Port 5985
Test-WSMan SERVER01                          # WinRM responding?
Invoke-Command SERVER01 { $env:COMPUTERNAME } # end-to-end
```
2. Failure decoder:
| Symptom | Cause | Fix |
|---|---|---|
| Cannot connect / port closed | WinRM not enabled on target | `Enable-PSRemoting -Force` on target (or via GPO for fleets) |
| Access denied | Not admin on target, or auth mode | Correct credentials; check `Get-PSSessionConfiguration` ACLs |
| Access denied cross-domain / workgroup | Kerberos unavailable, TrustedHosts empty | Add to `WSMan:\localhost\Client\TrustedHosts` or use HTTPS/cert auth |
| The second hop fails (accessing a share from within a session) | Credential delegation (double-hop) | CredSSP (cautiously) or resource-based constrained delegation |
| Works locally, not remotely, for CIM | Confusing WinRM (remoting) with DCOM (WMI) | `Get-CimInstance -CimSession` uses WSMan; `Get-WmiObject` uses DCOM (135+dynamic) |
3. Prefer `New-CimSession`/`New-PSSession` reuse over per-call connection for
   many queries against one host.
4. Security note: enabling remoting and TrustedHosts widens attack surface —
   scope via GPO, prefer HTTPS listeners, and never set `TrustedHosts = *`
   outside a lab.

## Related Entries
- V7.C1.E002 — CIM sessions · V1.C2.E007 — the DCOM alternative path

## References & Attribution
- MicrosoftDocs/PowerShell-Docs — Remoting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — failure decoder — License: n/a
