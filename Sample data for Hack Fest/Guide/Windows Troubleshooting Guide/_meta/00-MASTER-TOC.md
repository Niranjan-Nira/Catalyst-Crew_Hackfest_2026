# The Windows Troubleshooting Encyclopedia — Master Table of Contents



> **Edition:** 1.0 — all eleven volumes complete · Entries marked `[✓]` exist.
> Entry IDs follow the pattern `V<volume>.C<chapter>.E<entry>` — e.g., `V2.C2.E041` = Volume 2, Chapter 2, Kernel-Power Event 41.

---

## VOLUME I — Foundations of Windows Troubleshooting
### Chapter 1 — The Troubleshooting Discipline
- [✓] V1.C1.E001 — The Scientific Method Applied to Windows Failures
- [✓] V1.C1.E002 — Symptom vs. Cause: The Layered Diagnostic Model
- [✓] V1.C1.E003 — Reproducibility, Baselines, and Change Tracking
- [✓] V1.C1.E004 — First-Response Data Collection (what to grab before rebooting)
### Chapter 2 — Windows Architecture for Troubleshooters
- [✓] V1.C2.E001 — Session 0, Sessions, and Window Stations
- [✓] V1.C2.E002 — The Service Control Manager (SCM)
- [✓] V1.C2.E003 — The Boot Sequence: UEFI → Boot Manager → winload → Kernel → smss → Logon
- [✓] V1.C2.E004 — The Registry: Hives, Virtualization, and Transaction Logs
- [✓] V1.C2.E005 — NTFS, VSS, and the Storage Stack
- [✓] V1.C2.E006 — WMI/CIM Architecture and Repository Health
- [✓] V1.C2.E007 — COM, DCOM, and RPC Fundamentals
### Chapter 3 — The Diagnostic Toolbox
- [✓] V1.C3.E001 — Event Viewer (eventvwr) Deep Dive
- [✓] V1.C3.E002 — Reliability Monitor (perfmon /rel)
- [✓] V1.C3.E003 — Performance Monitor and Data Collector Sets
- [✓] V1.C3.E004 — Resource Monitor and Task Manager Internals
- [✓] V1.C3.E005 — Sysinternals Suite (ProcMon, ProcExp, Autoruns, PsTools)
- [✓] V1.C3.E006 — Windows Performance Recorder/Analyzer (WPR/WPA) and ETW
- [✓] V1.C3.E007 — DISM, SFC, and Component Store Repair
- [✓] V1.C3.E008 — msinfo32, dxdiag, and Hardware Inventory Tools
- [✓] V1.C3.E009 — Building Your Own Collector: PowerShell Diagnostic Automation

## VOLUME II — Event Viewer & The Event ID Reference
### Chapter 1 — How Windows Eventing Actually Works
- [✓] V2.C1.E001 — Why "All Event IDs Ever" Cannot Exist: The Provider-Manifest Model
- [✓] V2.C1.E002 — Anatomy of an Event: Provider, ID, Level, Keywords, Task, Opcode
- [✓] V2.C1.E003 — Channels: System, Application, Security, Setup, and Applications & Services
- [✓] V2.C1.E004 — Enumerating Every Provider and ID on a Machine (wevtutil, Get-WinEvent)
- [✓] V2.C1.E005 — Reading Event XML: EventData, UserData, and Rendering
- [✓] V2.C1.E006 — Filtering at Scale: XPath Queries and Structured Filtering
### Chapter 2 — System Log: Kernel, Power, and Boot Events
- [✓] V2.C2.E041 — Kernel-Power 41: The Unexpected Shutdown
- [✓] V2.C2.E1074 — User32 1074: Who Initiated the Restart
- [✓] V2.C2.E6005 — EventLog 6005/6006: Log Service Start/Stop as Boot Markers
- [✓] V2.C2.E6008 — EventLog 6008: The Dirty Shutdown Flag
- [✓] V2.C2.E109 — Kernel-Power 109: Kernel-Initiated Shutdown
- [✓] V2.C2.E142 — Kernel-Power 142/506/507: Modern Standby Transitions
### Chapter 3 — System Log: Service Control Manager Events
- [✓] V2.C3.E7000 — SCM 7000: Service Failed to Start
- [✓] V2.C3.E7001 — SCM 7001: Dependency Service Failure
- [✓] V2.C3.E7009 — SCM 7009: Service Start Timeout
- [✓] V2.C3.E7011 — SCM 7011: Transaction Response Timeout
- [✓] V2.C3.E7023 — SCM 7023: Service Terminated with Error
- [✓] V2.C3.E7031 — SCM 7031/7034: Service Crash and Recovery Action
- [✓] V2.C3.E7045 — SCM 7045: New Service Installed (security-relevant)
### Chapter 4 — System Log: Disk, Storage, and File System
- [✓] V2.C4.E007 — Disk 7: Bad Block
- [✓] V2.C4.E011 — Disk 11: Controller Error
- [✓] V2.C4.E051 — Disk 51: Paging Error
- [✓] V2.C4.E153 — Disk 153: IO Retried
- [✓] V2.C4.E055 — NTFS 55: File System Corruption
- [✓] V2.C4.E098 — NTFS 98: Volume Health / chkdsk Results
- [✓] V2.C4.E129 — storahci/stornvme 129: Reset to Device
### Chapter 5 — System Log: Networking Events
- [✓] V2.C5.E4227 — Tcpip 4227/4231: Port Exhaustion
- [✓] V2.C5.E5719 — NETLOGON 5719: No Domain Controller Available
- [✓] V2.C5.E1014 — DNS Client 1014: Name Resolution Timeout
- [✓] V2.C5.E10400 — NDIS and NIC Reset Events
- [✓] V2.C5.E8015 — DHCP-Client Address Conflict Family
### Chapter 6 — System Log: Time, Group Policy, and Directory Client
- [✓] V2.C6.E1058 — GroupPolicy 1058/1030: SYSVOL Access Failures
- [✓] V2.C6.E129 — Time-Service 129/134/47: Sync Failure Family
- [✓] V2.C6.E5722 — NETLOGON 5722: Machine Account Password Mismatch
### Chapter 7 — Application Log: Crashes and Hangs
- [✓] V2.C7.E1000 — Application Error 1000: The Application Crash
- [✓] V2.C7.E1001 — Windows Error Reporting 1001: The WER Bucket Record
- [✓] V2.C7.E1002 — Application Hang 1002
- [✓] V2.C7.E1026 — .NET Runtime 1026: Unhandled Managed Exception
- [✓] V2.C7.E1023 — .NET Runtime 1023: Fatal Execution Engine Error
### Chapter 8 — Application Log: MSI, Servicing, and Component Events
- [✓] V2.C8.E11707 — MsiInstaller 11707/11708/1033/1034: Install Success/Failure
- [✓] V2.C8.E1530 — User Profile Service 1530/1533/1511: Profile Load Failures
- [✓] V2.C8.E10016 — DistributedCOM 10016: The Most Over-Feared Event in Windows
- [✓] V2.C8.E455 — ESENT 455/489/490: Database Engine File Errors
### Chapter 9 — Security Log: Authentication (The 46xx Series)
- [✓] V2.C9.E4624 — 4624: Successful Logon (and all Logon Types 2–11)
- [✓] V2.C9.E4625 — 4625: Failed Logon (Status/Sub-Status code tables)
- [✓] V2.C9.E4634 — 4634/4647: Logoff Events
- [✓] V2.C9.E4648 — 4648: Explicit Credential Logon (runas / lateral movement)
- [✓] V2.C9.E4672 — 4672: Special Privileges Assigned
- [✓] V2.C9.E4768 — 4768/4769/4771: Kerberos TGT/Service Ticket/Pre-auth Failure
- [✓] V2.C9.E4776 — 4776: NTLM Credential Validation
### Chapter 10 — Security Log: Account and Policy Management
- [✓] V2.C10.E4720 — 4720–4726: Account Lifecycle
- [✓] V2.C10.E4728 — 4728/4732/4756: Group Membership Changes
- [✓] V2.C10.E4740 — 4740: Account Lockout
- [✓] V2.C10.E4719 — 4719: Audit Policy Changed
- [✓] V2.C10.E1102 — 1102: Audit Log Cleared
### Chapter 11 — Security Log: Process, Object, and System Integrity
- [✓] V2.C11.E4688 — 4688: Process Creation (with command-line auditing)
- [✓] V2.C11.E4663 — 4656/4663: Object Access
- [✓] V2.C11.E5140 — 5140/5145: Network Share Access
- [✓] V2.C11.E4697 — 4697: Service Installation (Security log counterpart of 7045)
- [✓] V2.C11.E6416 — 6416: New External Device Recognized
### Chapter 12 — Applications & Services Logs: The High-Value Channels
- [✓] V2.C12.E001 — TaskScheduler/Operational: 106/200/201/203 Task Lifecycle
- [✓] V2.C12.E002 — Windows Defender/Operational: 1116/1117/5001/5007
- [✓] V2.C12.E003 — PowerShell/Operational: 4103/4104 Script Block Logging
- [✓] V2.C12.E004 — TerminalServices: RDP Connection Chain (1149, 21, 24, 25)
- [✓] V2.C12.E005 — Diagnostics-Performance: 100–110 Boot Degradation Events
- [✓] V2.C12.E006 — WLAN-AutoConfig 8001/8002/8003: Wireless Connect/Disconnect
- [✓] V2.C12.E007 — Kernel-PnP 219/411: Device Start Failures
- [✓] V2.C12.E008 — CAPI2/Operational: Certificate Chain Failures
### Chapter 13 — Bugchecks and the Kernel
- [✓] V2.C13.E1001b — BugCheck 1001: Reading the Stop Code Record
- [✓] V2.C13.E002 — The Stop Code Families (0x0A, 0x1E, 0x3B, 0x50, 0x7E, 0x9F, 0xD1, 0x124, 0x133, 0x139, 0xEF)
- [✓] V2.C13.E003 — WHEA-Logger 17/18/19/47: Hardware Error Records

## VOLUME III — Windows Error Reporting (WER) & Crash Analysis
### Chapter 1 — WER Architecture
- [✓] V3.C1.E001 — The WER Pipeline: From Fault to Report to Microsoft
- [✓] V3.C1.E002 — Report Anatomy: Report.wer Field-by-Field Reference
- [✓] V3.C1.E003 — Bucketing: How Microsoft Groups Crashes (Fault Buckets Explained)
- [✓] V3.C1.E004 — Where Reports Live: ReportArchive, ReportQueue, and the Registry
- [✓] V3.C1.E005 — Event Types: AppCrash, AppHang, BEX/BEX64, CLR20r3, LiveKernelEvent, PnPDriver, and More
- [✓] V3.C1.E006 — Exception Code Reference: 0xC0000005 and the Other Codes That Matter
- [✓] V3.C1.E007 — Controlling WER: Group Policy, Registry, LocalDumps, and Corporate Collection
### Chapter 2 — Crash Dump Analysis
- [✓] V3.C2.E001 — Dump Types: Minidump, Kernel, Complete, Active, Triage
- [✓] V3.C2.E002 — WinDbg Setup, Symbols, and !analyze -v
- [✓] V3.C2.E003 — Reading a User-Mode Crash: Stack, Modules, Exception Context
- [✓] V3.C2.E004 — Reading a Kernel Bugcheck Dump
- [✓] V3.C2.E005 — LiveKernelEvents: Diagnosing Hangs Without a Blue Screen
### Chapter 3 — Reliability Data Programmatically
- [✓] V3.C3.E001 — Win32_ReliabilityRecords and Building Stability Reports
- [✓] V3.C3.E002 — Correlating WER, Event Log, and Reliability Monitor Records

## VOLUME IV — Windows Update: Architecture & Troubleshooting
### Chapter 1 — How Windows Update Works
- [✓] V4.C1.E001 — Update Types: Quality, Feature, Driver, Definition, OOB, Checkpoint Cumulative
- [✓] V4.C1.E002 — The Update Stack: USO, WU Agent, BITS/DO, Servicing Stack, CBS
- [✓] V4.C1.E003 — Delivery Optimization Deep Dive
- [✓] V4.C1.E004 — Servicing Channels, Deferral, and Update Rings
### Chapter 2 — Diagnosing Update Failures
- [✓] V4.C2.E001 — Reading WindowsUpdate.log (Get-WindowsUpdateLog) and CBS.log
- [✓] V4.C2.E002 — The 0x8007xxxx / 0x8024xxxx / 0x80D0xxxx Error Code Atlas
- [✓] V4.C2.E003 — Component Store Corruption: DISM RestoreHealth Workflows
- [✓] V4.C2.E004 — Stuck at N%: Install-Phase Failure Patterns
- [✓] V4.C2.E005 — Rollbacks and SetupDiag for Feature Update Failures
- [✓] V4.C2.E006 — Reset-WindowsUpdate: Safe Component Reset Procedure
### Chapter 3 — Managed Update Environments
- [✓] V4.C3.E001 — WSUS Troubleshooting
- [✓] V4.C3.E002 — Windows Update for Business / Autopatch
- [✓] V4.C3.E003 — Expedited Updates and Compliance Deadlines

## VOLUME V — Deployment & Management
### Chapter 1 — Imaging and Provisioning
- [✓] V5.C1.E001 — Windows ADK, WinPE, and Answer Files
- [✓] V5.C1.E002 — DISM Image Servicing Workflows
- [✓] V5.C1.E003 — Windows Autopilot: Profiles, Enrollment, and Failure Codes
- [✓] V5.C1.E004 — Provisioning Packages (PPKG)
### Chapter 2 — Modern Management
- [✓] V5.C2.E001 — Intune/MDM Enrollment Troubleshooting (DeviceManagement-Enterprise-Diagnostics-Provider)
- [✓] V5.C2.E002 — CSPs and the MDM Diagnostic Report
- [✓] V5.C2.E003 — Hybrid Join and Entra ID Device States (dsregcmd /status)
### Chapter 3 — Group Policy
- [✓] V5.C3.E001 — GP Processing Pipeline and gpresult /h
- [✓] V5.C3.E002 — GP Event IDs 4016/5016/7016/8000-series
- [✓] V5.C3.E003 — Common GPO Failures: Slow Link, Loopback, Security Filtering

## VOLUME VI — Security Configuration
### Chapter 1 — Baseline Hardening
- [✓] V6.C1.E001 — Microsoft Security Baselines and LGPO
- [✓] V6.C1.E002 — Audit Policy Design (what to enable and why)
- [✓] V6.C1.E003 — Credential Protection: LSA, Credential Guard, LAPS
- [✓] V6.C1.E004 — BitLocker: Deployment, Recovery, and Event IDs (24620-series)
- [✓] V6.C1.E005 — AppLocker / WDAC Fundamentals
- [✓] V6.C1.E006 — Attack Surface Reduction Rules and Their Event IDs
### Chapter 2 — Defender Stack
- [✓] V6.C2.E001 — Microsoft Defender Antivirus Configuration and Ops Events
- [✓] V6.C2.E002 — Defender Firewall: Profiles, Rules, and Log Analysis
- [✓] V6.C2.E003 — SmartScreen and Exploit Protection

## VOLUME VII — PowerShell for Administration & Diagnostics
### Chapter 1 — The Diagnostic Cmdlet Reference
- [✓] V7.C1.E001 — Get-WinEvent Mastery (FilterHashtable, FilterXml, Oldest)
- [✓] V7.C1.E002 — CIM Cmdlets: Get-CimInstance Patterns for Hardware/OS Inventory
- [✓] V7.C1.E003 — Process/Service/Task Cmdlets
- [✓] V7.C1.E004 — Network Diagnostics: Test-NetConnection and the NetTCPIP Module
- [✓] V7.C1.E005 — Storage Cmdlets and SMART Data
- [✓] V7.C1.E006 — Update, Defender, BitLocker, and Firewall Modules
### Chapter 2 — Automation Patterns
- [✓] V7.C2.E001 — Background Jobs vs. Runspaces for Concurrent Collection
- [✓] V7.C2.E002 — Robust Error Handling and Transcript Logging
- [✓] V7.C2.E003 — Packaging Diagnostic Output (Compress-Archive, status manifests)
- [✓] V7.C2.E004 — Remoting: WinRM Configuration and Troubleshooting

## VOLUME VIII — Networking & Connectivity
### Chapter 1 — Name Resolution
- [✓] V8.C1.E001 — The Resolution Order: HOSTS, DNS Cache, DNS, LLMNR/NetBIOS, mDNS
- [✓] V8.C1.E002 — Diagnosing DNS: nslookup vs. Resolve-DnsName, and Reading Failures
- [✓] V8.C1.E003 — DNS Cache and Negative Caching Pitfalls
### Chapter 2 — Connectivity and Transport
- [✓] V8.C2.E001 — The Connectivity Ladder: Link → IP → Gateway → DNS → Service
- [✓] V8.C2.E002 — NCSI and the "No Internet" / Captive Portal Logic
- [✓] V8.C2.E003 — TCP Diagnostics: Test-NetConnection, Ports, and Path
### Chapter 3 — Proxy, VPN, and Edge Cases
- [✓] V8.C3.E001 — Proxy Layers: WinINET vs. WinHTTP vs. Per-App
- [✓] V8.C3.E002 — VPN and Always On VPN Troubleshooting
- [✓] V8.C3.E003 — TLS/SSL Inspection and Certificate-Trust Failures

## VOLUME IX — Performance, Storage & Boot
### Chapter 1 — Slow Boot and Logon Analysis
- [✓] V9.C1.E001 — Decomposing Boot: The Free-Tier Method (Diagnostics-Performance)
- [✓] V9.C1.E002 — Slow Logon: Profiles, GP, and Scripts
- [✓] V9.C1.E003 — Deep Boot Tracing with WPR/WPA
### Chapter 2 — Memory, Handle, and Resource Leaks
- [✓] V9.C2.E001 — Diagnosing High Memory: Working Set, Commit, and Pools
- [✓] V9.C2.E002 — Handle and GDI/User Object Leaks
- [✓] V9.C2.E003 — High CPU Attribution
### Chapter 3 — Disk Latency and Storage Performance
- [✓] V9.C3.E001 — Measuring Disk Latency the Right Way
- [✓] V9.C3.E002 — What's Hitting the Disk: Attribution and Antivirus
- [✓] V9.C3.E003 — Memory Pressure and the Paging Connection

## VOLUME X — Application Support & Compatibility
### Chapter 1 — Compatibility Mechanisms
- [✓] V10.C1.E001 — Shims and the Application Compatibility Toolkit
- [✓] V10.C1.E002 — UAC, Virtualization, and Per-User vs. Per-Machine Installs
- [✓] V10.C1.E003 — Diagnosing "Works for Admin, Not for User" and DLL/Runtime Issues
### Chapter 2 — Application Patterns
- [✓] V10.C2.E001 — Office Troubleshooting (Safe Mode, Add-ins, Repair)
- [✓] V10.C2.E002 — Browser and Edge/WebView2 Patterns
- [✓] V10.C2.E003 — Line-of-Business App Deployment and Failure Triage

## VOLUME XI — Sources, Licensing & Attribution
- [✓] V11.C1.E001 — Source Registry: Documentation Repositories Used
- [✓] V11.C1.E002 — License Retention Policy (CC BY 4.0 and Microsoft Docs terms)
- [✓] V11.C1.E003 — Attribution Format for Generated Records

