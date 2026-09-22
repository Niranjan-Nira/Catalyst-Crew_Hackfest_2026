# Volume VII · Chapter 1 — The Diagnostic Cmdlet Reference

The cmdlets this encyclopedia leans on throughout, gathered with their sharp
edges. Guiding choices: prefer CIM over WMI cmdlets (WSMan transport, no
DCOM), prefer structured objects over text parsing, and always
filter/query server-side where the cmdlet allows.

---
entry_id: V7.C1.E001
title: "Get-WinEvent Mastery (FilterHashtable, FilterXml, Oldest)"
category: reference
severity_for_triage: informational
applies_to: ["Windows 7+/Server 2008 R2+ with PowerShell"]
sources:
  - repo: "MicrosoftDocs/PowerShell-Docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`Get-WinEvent` is the backbone of every event query in this encyclopedia.
`Get-EventLog` is legacy (classic logs only, slow, no modern channels) — do
not use it. The performance rule is absolute: **filter server-side** with
`-FilterHashtable`/`-FilterXPath`/`-FilterXml`; piping to `Where-Object` pulls
every event into memory first and is orders of magnitude slower on large logs.

## Message Text & Fields — the patterns
**FilterHashtable keys** (AND-combined): `LogName`, `ProviderName`, `Id`,
`Level` (1 Crit, 2 Err, 3 Warn, 4 Info, 5 Verbose), `StartTime`, `EndTime`,
`Keywords` (a *long* bitmask — for the Security log's Audit Failure use
`4503599627370496`), `Path` (for offline `.evtx`), and `Data`/named EventData
values on newer builds.

```powershell
# Canonical: errors+critical in System, last 24h
Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=(Get-Date).AddDays(-1)}

# Offline .evtx from another machine
Get-WinEvent -Path C:\Diag\System.evtx -FilterXPath "*[System[(EventID=41)]]"

# Reading a legacy/huge log oldest-first without loading it all
Get-WinEvent -LogName System -Oldest -MaxEvents 100
```

## Meaning — the field-extraction idiom
The rendered `.Message` is locale- and template-dependent; parse the XML by
field name (the pattern used everywhere in this work):
```powershell
$e = Get-WinEvent -FilterHashtable @{LogName='System'; Id=7000} -MaxEvents 1
$d = ([xml]$e.ToXml()).Event.EventData.Data
($d | Where-Object Name -eq 'param1').'#text'
```

## Diagnostic Procedure — traps to avoid
1. **No-match error:** `Get-WinEvent` throws "No events were found" as a
   terminating-ish error; wrap fleet loops with `-ErrorAction SilentlyContinue`
   and treat empty as data.
2. **Level for Security:** Security events are Level 0 (Information) with
   Audit Success/Failure carried in **Keywords**, not Level — filtering
   Security by `Level=2` returns nothing.
3. **Provider vs. LogName:** an ID means nothing without its provider
   (V2.C1.E001) — include `ProviderName` whenever an ID is ambiguous
   (129, 1001, 1000…).
4. **Speed check:** if a query is slow, you are almost certainly filtering
   client-side — move the predicate into the hashtable or XPath.

## Related Entries
- V2.C1.E004 — provider/ID enumeration · V2.C1.E006 — XPath at scale

## References & Attribution
- MicrosoftDocs/PowerShell-Docs — Get-WinEvent — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — trap list — License: n/a

---
entry_id: V7.C1.E002
title: "CIM Cmdlets: Get-CimInstance Patterns for Hardware/OS Inventory"
category: reference
severity_for_triage: informational
applies_to: ["Windows 7+/Server 2008 R2+ (PowerShell 3+)"]
sources:
  - repo: "MicrosoftDocs/PowerShell-Docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`Get-CimInstance` replaced `Get-WmiObject` (removed from PowerShell 7): same
information, WSMan transport instead of DCOM, better filtering, no COM
fragility. The inventory workhorses and their high-value classes are worth
memorizing because they appear in every diagnostic package.

## Message Text & Fields — the inventory shortlist
| Class | Yields |
|---|---|
| `Win32_OperatingSystem` | Build, install date, last boot (uptime), free memory |
| `Win32_ComputerSystem` | Model, manufacturer, domain, total RAM, logical processors |
| `Win32_BIOS` / `Win32_BaseBoard` | Firmware version/date, serial, board |
| `Win32_Processor` | CPU model, cores, current clock |
| `Win32_PhysicalMemory` | Per-DIMM size, speed, slot, manufacturer |
| `Win32_LogicalDisk` / `MSFT_PhysicalDisk` (Storage) | Volumes / physical health |
| `Win32_PnPEntity` | Devices; `ConfigManagerErrorCode` for error states |
| `Win32_Service` | Services with StartName/PathName/State |
| `Win32_Product` | **Avoid** — triggers MSI reconfiguration; use registry uninstall keys instead |
| `Win32_ReliabilityRecords` | The Reliability Monitor feed (V1.C3.E002) |

## Diagnostic Procedure
1. Filter server-side with the `-Filter` (WQL) parameter, not `Where-Object`:
```powershell
Get-CimInstance Win32_Service -Filter "State='Running' AND StartMode='Auto'"
```
2. Uptime the correct way:
```powershell
(Get-CimInstance Win32_OperatingSystem).LastBootUpTime
```
3. Remote query over WSMan (no DCOM holes to open):
```powershell
$s = New-CimSession -ComputerName SERVER01
Get-CimInstance Win32_OperatingSystem -CimSession $s | Select-Object Caption, Version
```
4. Trap: `Win32_Product` enumeration is notorious for firing MSI
   self-repair on every installed product — never use it for "list installed
   software"; read the registry uninstall hives (V1.C1.E003) instead.

## Related Entries
- V1.C2.E006 — WMI/CIM architecture · V1.C3.E008 — inventory tooling

## References & Attribution
- MicrosoftDocs/PowerShell-Docs — CIM cmdlets — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — class shortlist, Win32_Product warning — License: n/a

---
entry_id: V7.C1.E003
title: "Process, Service, and Task Cmdlets"
category: reference
severity_for_triage: informational
applies_to: ["Windows PowerShell 5.1 / PowerShell 7"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The control surface for the live system. Know which cmdlet gives which detail:
`Get-Process` for memory/CPU/handles but **not** the command line or owner —
those come from `Get-CimInstance Win32_Process`; `Get-Service` for state but
not the logon account or binary path — those from `Win32_Service`.

## Diagnostic Procedure
1. Processes with command line and owner (the forensic view):
```powershell
Get-CimInstance Win32_Process | Select-Object ProcessId, Name, CommandLine,
  @{n='Owner';e={ (Invoke-CimMethod $_ -MethodName GetOwner).User }}
```
2. Handle/memory leak hunting:
```powershell
Get-Process | Sort-Object HandleCount -Descending |
  Select-Object -First 10 Name, Id, HandleCount, @{n='WS_MB';e={[int]($_.WS/1MB)}}
```
3. Services with their real identity:
```powershell
Get-CimInstance Win32_Service |
  Select-Object Name, State, StartMode, StartName, PathName
```
4. Scheduled tasks and last results (ties to V2.C12.E001):
```powershell
Get-ScheduledTask | Get-ScheduledTaskInfo |
  Select-Object TaskName, LastRunTime, LastTaskResult, NextRunTime |
  Where-Object LastTaskResult -ne 0
```

## Related Entries
- V2.C7 — crash/hang events · V2.C3 — service events · V2.C12.E001 — tasks

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V7.C1.E004
title: "Network Diagnostics: Test-NetConnection and the NetTCPIP Module"
category: reference
severity_for_triage: informational
applies_to: ["Windows 8+/Server 2012+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The modern replacements for ping/tracert/netstat that return *objects*.
`Test-NetConnection` is the swiss-army probe (ICMP, TCP port, route, and
diagnostics in one); the `NetTCPIP`/`NetAdapter`/`DnsClient` modules expose
the whole stack as queryable data — the backbone of the Chapter 5 networking
procedures.

## Diagnostic Procedure
1. Reachability + specific port + path in one call:
```powershell
Test-NetConnection dc01.corp.com -Port 389 -InformationLevel Detailed
```
2. Connections mapped to processes (the port-exhaustion view, V2.C5.E4227):
```powershell
Get-NetTCPConnection -State Established |
  Group-Object OwningProcess | Sort-Object Count -Descending |
  Select-Object -First 10 Count, @{n='Proc';e={(Get-Process -Id $_.Name -EA SilentlyContinue).ProcessName}}
```
3. Adapter and DNS state:
```powershell
Get-NetAdapter | Select-Object Name, Status, LinkSpeed, DriverVersion
Get-DnsClientServerAddress -AddressFamily IPv4
Resolve-DnsName problem.name -Server 10.0.0.10
```
4. Trap: `Test-NetConnection` ICMP can fail while TCP succeeds (firewalls drop
   ping, allow the service) — always test the actual port, not just `-Ping`.

## Related Entries
- V2.C5.* — the networking event chapter

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V7.C1.E005
title: "Storage Cmdlets and SMART Data"
category: reference
severity_for_triage: informational
applies_to: ["Windows 8+/Server 2012+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The Storage module turns "is this disk dying?" (the Chapter 4 question) into
data. Physical health, reliability counters, volume state, and partition
mapping without third-party tools.

## Diagnostic Procedure
1. Physical disk health + wear + errors (the SMART-adjacent view):
```powershell
Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, BusType,
  HealthStatus, OperationalStatus
Get-PhysicalDisk | Get-StorageReliabilityCounter |
  Select-Object DeviceId, Wear, Temperature, PowerOnHours,
    ReadErrorsUncorrected, WriteErrorsUncorrected
```
2. Volume health and free space:
```powershell
Get-Volume | Select-Object DriveLetter, FileSystemLabel, HealthStatus,
  @{n='Free_GB';e={[int]($_.SizeRemaining/1GB)}}, @{n='Size_GB';e={[int]($_.Size/1GB)}}
```
3. Map a `HarddiskN` from a disk event (V2.C4) to a volume:
```powershell
Get-Partition -DiskNumber 1 | Select-Object DriveLetter, Size, Type
```
4. Note: `ReadErrorsUncorrected`/`Wear` availability depends on the drive and
   driver exposing counters; missing values are a data gap to record, not a
   clean bill of health.

## Related Entries
- V2.C4.* — storage events · V1.C3.E008 — hardware inventory

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V7.C1.E006
title: "Update, Defender, BitLocker, and Firewall Modules"
category: reference
severity_for_triage: informational
applies_to: ["Windows 10/11, Server 2016+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The security-and-servicing module surface — the programmatic side of Volumes
IV and VI. None require third-party modules; all ship in-box.

## Diagnostic Procedure
1. Update posture (no PSWindowsUpdate needed for read-only checks):
```powershell
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10
Get-Service wuauserv, UsoSvc, DoSvc, BITS | Select-Object Name, Status
Get-DeliveryOptimizationStatus | Select-Object FileId, BytesFromPeers, BytesFromHttp, Status
```
2. Defender (Volume VI companion):
```powershell
Get-MpComputerStatus | Select-Object AMRunningMode, RealTimeProtectionEnabled,
  AntivirusSignatureLastUpdated, QuickScanEndTime
Get-MpPreference | Select-Object ExclusionPath, ExclusionProcess, DisableRealtimeMonitoring
Get-MpThreatDetection | Select-Object -First 10 ThreatID, InitialDetectionTime, Resources
```
3. BitLocker:
```powershell
Get-BitLockerVolume | Select-Object MountPoint, VolumeStatus, ProtectionStatus,
  EncryptionPercentage, EncryptionMethod
(Get-BitLockerVolume -MountPoint C:).KeyProtector |
  Select-Object KeyProtectorType, KeyProtectorId   # recovery-key IDs
```
4. Firewall:
```powershell
Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction
Get-NetFirewallRule -Enabled True -Direction Inbound |
  Where-Object Action -eq 'Allow' | Select-Object DisplayName, Profile -First 20
```

## Related Entries
- V4.* — update volume · V6.* — security configuration volume · V2.C12.E002 — Defender events

## References & Attribution
- original synthesis — License: n/a
