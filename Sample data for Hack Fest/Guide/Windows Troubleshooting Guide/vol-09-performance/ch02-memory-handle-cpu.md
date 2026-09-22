# Volume IX · Chapter 2 — Memory, Handle, and Resource Leaks

"The machine gets slow after a few days and a reboot fixes it" is the leak
signature. The skill is naming *which* resource is leaking (working set,
commit, pool, handles, GDI) and *which* process owns it — because each has a
different limit and a different fix.

---
entry_id: V9.C2.E001
title: "Diagnosing High Memory: Working Set, Commit, and Pools"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11, Server 2016+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
"Out of memory" is several distinct conditions. **Working set** = physical RAM
a process currently uses (reclaimable under pressure). **Commit** = total
virtual memory promised (RAM + page file) — hitting the *commit limit* is the
real "system out of memory," independent of physical RAM. **Kernel pools**
(paged/nonpaged) are a separate, smaller budget that drivers exhaust — a
classic server crasher (bugcheck `0x0` pool-related family). Diagnose the right
one.

## Diagnostic Procedure
1. System-wide picture — is it commit, physical, or pool?
```powershell
$os = Get-CimInstance Win32_OperatingSystem
[pscustomobject]@{
  FreePhys_MB   = [int]($os.FreePhysicalMemory/1KB)
  CommitUsed_MB = [int](($os.TotalVirtualMemorySize - $os.FreeVirtualMemory)/1KB)
  CommitLimit_MB= [int]($os.TotalVirtualMemorySize/1KB)
}
Get-Counter '\Memory\Committed Bytes','\Memory\Commit Limit',
  '\Memory\Pool Nonpaged Bytes','\Memory\Pool Paged Bytes'
```
2. Top process by working set, and by commit (private bytes):
```powershell
Get-Process | Sort-Object WS -Descending | Select-Object -First 10 Name, Id,
  @{n='WS_MB';e={[int]($_.WS/1MB)}}, @{n='Private_MB';e={[int]($_.PrivateMemorySize64/1MB)}}
```
3. **Pool exhaustion** — when nonpaged/paged pool climbs, find the tag with
   `poolmon` (from the WDK): sort by bytes, note the 4-char tag, map it to a
   driver with `findstr` against `pooltag.txt` or `!poolused` in a kernel dump.
   Pool leaks are almost always a driver, not an app.
4. Leak vs. load: sample private bytes over hours — monotonic climb in one PID
   = leak (capture a dump with PageHeap/UMDH for the vendor); sawtooth = normal
   load.

## Related Entries
- V9.C2.E002 — handle/GDI leaks · V9.C3.E003 — the paging consequence

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V9.C2.E002
title: "Handle and GDI/User Object Leaks"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Some "slow over time" problems aren't memory at all. **Handle leaks** (kernel
objects — files, events, registry keys never closed) and **GDI/User object
leaks** (per-session graphics/window objects, capped at ~10,000 per process by
default) degrade or crash an app long before RAM runs out. The symptom: one
process's handle or GDI count climbs without bound; the app eventually fails to
create windows/menus or crashes.

## Diagnostic Procedure
1. Handle-count trend (the leak fingerprint):
```powershell
Get-Process | Sort-Object HandleCount -Descending |
  Select-Object -First 10 Name, Id, HandleCount
# sample repeatedly for one PID:
1..6 | ForEach-Object { (Get-Process -Id 1234).HandleCount; Start-Sleep 60 }
```
2. GDI/User objects (add the columns in Task Manager → Details, or):
```powershell
Add-Type -TypeDefinition @"
using System;using System.Runtime.InteropServices;
public class U{[DllImport("user32.dll")]public static extern int GetGuiResources(IntPtr h,int f);}
"@
$p=Get-Process -Id 1234
"GDI=$([U]::GetGuiResources($p.Handle,0))  USER=$([U]::GetGuiResources($p.Handle,1))"
```
   Approaching 10,000 GDI objects = the leak; the app will soon fail to draw.
3. Identify *what kind* of handle leaks with Process Explorer (lower pane →
   Handles view) — the dominant handle type (Event, File, Key) points at the
   code path; hand the finding to the vendor.

## Related Entries
- V9.C2.E001 — memory leaks · V1.C3.E005 — Process Explorer

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V9.C2.E003
title: "High CPU Attribution"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11, Server 2016+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
High CPU has three culprit classes with different tools: a **user process**
(easy — name it and look at its threads), a **service inside svchost** (need to
find *which* hosted service), or the **kernel/System process** (drivers,
interrupts — the hardest, needs stack sampling).

## Diagnostic Procedure
1. Top CPU consumers:
```powershell
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, Id, CPU,
  @{n='WS_MB';e={[int]($_.WS/1MB)}}
```
2. **svchost** high CPU — find the hosted service:
```powershell
$pid = 1234
Get-CimInstance Win32_Service -Filter "ProcessId=$pid" | Select-Object Name, DisplayName
tasklist /svc /fi "PID eq $pid"
```
   Then narrow to the thread (Process Explorer → the svchost → Threads tab
   shows the busy thread's start module).
3. **System / "System interrupts"** high CPU = driver or interrupt storm:
   this is a WPR/WPA job (V1.C3.E006) — capture CPU-sampled with stacks and
   read the DPC/ISR or driver module burning time. Common causes: a
   misbehaving NIC/storage/USB driver (correlate with the reset events in
   V2.C4/C5).
4. Sustained 100% with a normal-looking top process can be **thermal
   throttling masking** or a background maintenance task
   (Diagnostics-Performance/maintenance) — check scheduled maintenance and
   `powercfg` throttle state.

## Related Entries
- V1.C2.E002 — svchost grouping · V1.C3.E006 — WPA for kernel CPU · V2.C4.E129 — driver reset storms

## References & Attribution
- original synthesis — License: n/a
