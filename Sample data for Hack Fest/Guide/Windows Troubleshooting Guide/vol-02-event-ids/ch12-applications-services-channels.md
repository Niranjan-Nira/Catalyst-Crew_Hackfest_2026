# Volume II · Chapter 12 — Applications & Services Logs: The High-Value Channels

The classic System/Application logs are summaries; the component channels under
Applications & Services carry the detail. These eight channels repay knowing by
heart. All are enabled by default unless noted; export any of them with
`wevtutil epl <channel> <file.evtx>` for offline work.

---
entry_id: V2.C12.E001
title: "TaskScheduler/Operational: 106/200/201/203 Task Lifecycle"
category: event-id
event: { id: 201, provider: "Microsoft-Windows-TaskScheduler", channel: "Microsoft-Windows-TaskScheduler/Operational", level: Information }
severity_for_triage: medium
applies_to: ["Windows 7+/Server 2008 R2+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Every scheduled task narrates its life here: `106` task registered (who
created what — persistence auditing), `100` task started, `200` action
started, `201` action completed **with the return code**, `203` failed to
launch, `101` start failed, `102` completed. The channel answers both "did my
job run and succeed?" and "what new tasks appeared on this machine?"

## Meaning
The `201` return code is the process exit code — `0` success by convention,
but the *task* status can show `0x1` etc. from the program itself; decode in
the program's own terms. Launch failures (`203`/`101`) embed error codes:
`0x80070005` access denied (changed service-account rights), `0x8007010B`
invalid working directory (deleted path), `2147943645` (`0x800710E0`)
"user not logged on" for tasks requiring an interactive session.

Note: on current builds this channel may be disabled by default — if empty,
check `IsEnabled` and turn it on before concluding "no tasks ran."

## Diagnostic Procedure
1. History of one task:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational'} -MaxEvents 400 |
  Where-Object { $_.Message -like '*\MyTask*' } |
  Select-Object TimeCreated, Id, Message
```
2. Cross-check task definition and last result:
```powershell
Get-ScheduledTask -TaskName MyTask | Get-ScheduledTaskInfo
```
3. New registrations for persistence review (pair with 7045/4698):
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational'; Id=106} -MaxEvents 20 |
  Select-Object TimeCreated, Message
```

## Related Entries
- V2.C3.E7045 — service persistence sibling · V2.C10 — Security 4698 family

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C12.E002
title: "Windows Defender/Operational: 1116/1117/5001/5007"
category: event-id
event: { id: 1116, provider: "Microsoft-Windows-Windows Defender", channel: "Microsoft-Windows-Windows Defender/Operational", level: Warning }
severity_for_triage: high
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
Defender's working log. The IDs that matter: `1116` malware **detected**,
`1117` action **taken** (the pair — a 1116 without a 1117 deserves attention),
`1118/1119` action failed, `5001` real-time protection **disabled**, `5004`
RTP configuration changed, `5007` **platform configuration changed** (the
audit trail of exclusions and policy edits), `2000/2001` definition updates,
`1000/1001/1002` scan start/stop/cancel.

## Meaning
Two distinct uses: threat triage (1116/1117: what, where, action, user) and
tamper/health auditing — `5001` and `5007` are the events that catch both
malware disabling protection and admins adding overly broad exclusions.
A 5007 diff includes old and new values: exclusions added to
`Exclusions\Paths` are readable right in the message.

## Diagnostic Procedure
1. Detection history with actions:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational'; Id=1116,1117} -MaxEvents 20 |
  Select-Object TimeCreated, Id, Message | Format-List
```
2. Tamper/exclusion audit:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational'; Id=5001,5007} -MaxEvents 30 |
  Select-Object TimeCreated, Id, Message
```
3. Current posture:
```powershell
Get-MpComputerStatus | Select-Object AMRunningMode, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated
Get-MpPreference | Select-Object ExclusionPath, ExclusionProcess, DisableRealtimeMonitoring
```

## Related Entries
- V6.C2.E001 — Defender configuration (queued)

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — Defender event IDs — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — auditing use — License: n/a

---
entry_id: V2.C12.E003
title: "PowerShell/Operational: 4103/4104 Script Block Logging"
category: event-id
event: { id: 4104, provider: "Microsoft-Windows-PowerShell", channel: "Microsoft-Windows-PowerShell/Operational", level: "Verbose/Warning" }
severity_for_triage: high
applies_to: ["PowerShell 5.0+ (Windows PowerShell); PowerShell 7 logs to PowerShellCore/Operational"]
sources:
  - repo: "MicrosoftDocs/PowerShell-Docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`4104` records the **content of script blocks as they compile** — the actual
code that ran, after de-obfuscation layers unwrap themselves (each layer
compiles, each compilation logs). `4103` records pipeline execution with
module logging. Even with policy off, PowerShell logs *suspicious* script
blocks at Warning level automatically. This channel is simultaneously an IR
goldmine and a troubleshooting tool for "what did that script actually do."

## Meaning
Keys: `4104` Level Verbose = policy-enabled full logging; Level **Warning** =
the engine's own suspicion heuristics fired (worth reviewing even in
unmanaged environments). Long scripts split across multiple 4104s with
sequence numbers — reassemble by ScriptBlockId. `4103` adds per-command
context (user, host application, command with bound parameters) when module
logging is on. Enablement lives in GPO: *Turn on PowerShell Script Block
Logging* (+ optionally transcription).

## Diagnostic Procedure
1. Recent auto-flagged (Warning) blocks — cheap hunting on any machine:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-PowerShell/Operational'; Id=4104; Level=3} -MaxEvents 20 |
  Select-Object TimeCreated, Message | Format-List
```
2. Reconstruct a specific script:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-PowerShell/Operational'; Id=4104} -MaxEvents 500 |
  Where-Object Message -like '*<distinctive string>*' |
  Sort-Object RecordId | Select-Object -Expand Message
```
3. Confirm policy state:
```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging' -ErrorAction SilentlyContinue
```

## Related Entries
- V2.C11.E4688 — process creation with command lines (queued)

## References & Attribution
- MicrosoftDocs/PowerShell-Docs — logging — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — hunting patterns — License: n/a

---
entry_id: V2.C12.E004
title: "TerminalServices: The RDP Connection Chain (1149, 21–25, 39/40)"
category: event-id
event: { id: 1149, provider: "Microsoft-Windows-TerminalServices-RemoteConnectionManager", channel: "Microsoft-Windows-TerminalServices-RemoteConnectionManager/Operational", level: Information }
severity_for_triage: medium
applies_to: ["Windows 7+/Server 2008 R2+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
One RDP session touches **three channels**, and reconstructing a session means
walking the chain: `RemoteConnectionManager/Operational` `1149` (network
connection accepted + source IP — pre-authentication, so 1149 alone proves
reachability, *not* successful logon) → Security `4624 Type 10` (the actual
authentication) → `LocalSessionManager/Operational` `21` session logon, `22`
shell start, `24` disconnect, `25` **reconnect**, `23` logoff, `39/40` session
X disconnected by session Y / disconnect reason code.

## Meaning
Session forensics questions this chain answers: who connected, from where,
when they disconnected vs. logged off (a disconnected session keeps running —
processes, locks, credentials in memory), and whether someone *reconnected* to
an abandoned session (25 after a long gap). Reason codes on 40: 0/5/11
normal-ish; 12 logoff. Brute-force noise appears as 1149 floods or Security
4625 Type 3/10 — pure 1149 floods without 4624s = scanning.

## Diagnostic Procedure
1. Session chain for the last week:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TerminalServices-LocalSessionManager/Operational'; Id=21,22,23,24,25} -MaxEvents 100 |
  Select-Object TimeCreated, Id, Message | Sort-Object TimeCreated
```
2. Source addresses:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TerminalServices-RemoteConnectionManager/Operational'; Id=1149} -MaxEvents 50 |
  Select-Object TimeCreated, Message
```
3. Correlate with Security 4624/4625 LogonType 10 for the auth verdicts.

## Related Entries
- V2.C9.E4624 — Type 10 sessions and credential exposure

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C12.E005
title: "Diagnostics-Performance: 100–110 Boot Degradation Events"
category: event-id
event: { id: 100, provider: "Microsoft-Windows-Diagnostics-Performance", channel: "Microsoft-Windows-Diagnostics-Performance/Operational", level: "Warning/Error/Critical" }
severity_for_triage: medium
applies_to: ["Windows Vista+ clients"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Windows grades its own boots. `100` fires for every boot with the full timing
breakdown (BootTime, MainPathBootTime, PostBootTime in ms — Level escalates
as boot degrades); `101–110` are the *blame* events, each naming a specific
offender: `101` application slowed boot (names the app), `102` driver slowed
device init, `103` service start degradation, `106` background prefetch
issue, `108` device init delay, `109` device degradation at shutdown-side.
Shutdown gets the same treatment (`200` series), standby `300` series.

## Meaning
This channel is the free tier of boot analysis — before reaching for WPR
(V1.C3.E006), read what Windows already measured: a `103` naming the same
service every boot, or a `102` naming a driver, is the answer without a trace.
MainPathBootTime is the OS-to-desktop core; PostBootTime is the settle period
(startup apps) — user complaints of "slow boot" are frequently PostBoot
(startup bloat), a different fix than MainPath (drivers/services).

## Diagnostic Procedure
1. Boot-time trend:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=100} -MaxEvents 20 |
  ForEach-Object { $d=([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{ Time=$_.TimeCreated
      BootMs=($d|? Name -eq 'BootTime').'#text'
      MainMs=($d|? Name -eq 'MainPathBootTime').'#text'
      PostMs=($d|? Name -eq 'PostBootTime').'#text' } }
```
2. The blame list:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=101,102,103,106,108,109} -MaxEvents 40 |
  Select-Object TimeCreated, Id, Message
```

## Related Entries
- V1.C3.E006 — WPR when this isn't enough · V9.* — performance volume (queued)

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C12.E006
title: "WLAN-AutoConfig 8001/8002/8003: Wireless Connect/Disconnect"
category: event-id
event: { id: 8003, provider: "Microsoft-Windows-WLAN-AutoConfig", channel: "Microsoft-Windows-WLAN-AutoConfig/Operational", level: Information }
severity_for_triage: medium
applies_to: ["Windows 7+ clients"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The Wi-Fi state machine's diary: `8001` connected (SSID, BSSID, band, auth,
cipher), `8002` connection **failed** (with failure reason), `8003`
disconnected (**with reason code** — the field that separates "user left" from
"driver died"), `11001/11005` auth started/succeeded, `12011–12013` 802.1X
outcomes, `20019` roam. For "Wi-Fi keeps dropping" complaints this channel
plus one command is usually the whole investigation.

## Meaning
8003 reason patterns: explicit disconnects (user/profile change) vs.
`0x8`-class radio/driver resets vs. AP-initiated deauth. Serial 8003/8001
pairs on the *same* BSSID = unstable link (driver/AP); pairs across BSSIDs =
roaming behavior (aggressiveness settings, AP power). 8002 with 802.1X events
= RADIUS/cert problems, not radio — pivot to CAPI2 (E008) for cert chains.

## Diagnostic Procedure
1. Connection stability history:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-WLAN-AutoConfig/Operational'; Id=8001,8002,8003} -MaxEvents 60 |
  Select-Object TimeCreated, Id, Message
```
2. The built-in wireless report (the underrated one-shot):
```cmd
netsh wlan show wlanreport
```
   → `C:\ProgramData\Microsoft\Windows\WlanReport\wlan-report-latest.html` —
   graphs sessions, disconnect reasons, and errors over 3 days.
3. Driver/radio facts: `netsh wlan show drivers` and `show interfaces`.

## Related Entries
- V2.C12.E008 — CAPI2 for 802.1X cert failures · V8.* — networking volume

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C12.E007
title: "Kernel-PnP 219/411: Device Start Failures"
category: event-id
event: { id: 219, provider: "Microsoft-Windows-Kernel-PnP", channel: System, level: Warning }
severity_for_triage: medium
applies_to: ["Windows 8+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Plug-and-Play's failure records: `219` — "The driver \Driver\X failed to load
for the device <instance path>" (logged to **System**) and the
`Kernel-PnP/Configuration` channel's `400/410/411/420` device
configure/start/fail/delete lifecycle. Together with Device Manager problem
codes (ConfigManagerErrorCode — see V1.C3.E008) they explain yellow-bang
devices and boot-time driver load failures.

## Meaning
The instance path in the event identifies the exact device
(`USB\VID_...`, `PCI\VEN_...`). Recurring 219 for the same device every boot:
driver/firmware mismatch, or a filter driver (classguard, encryption, USB
filter) blocking the stack — check the device's UpperFilters/LowerFilters
registry values, a classic invisible cause after security-software removal
leaves orphaned filters.

## Diagnostic Procedure
1. Recent PnP failures:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-PnP'; Id=219} -MaxEvents 20 |
  Select-Object TimeCreated, Message
```
2. Devices currently in error + their problem codes:
```powershell
Get-PnpDevice -Status Error | Select-Object FriendlyName, InstanceId, Problem
```
3. Filter check for the affected device class (example: disk class GUID):
```cmd
reg query "HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e967-e325-11ce-bfc1-08002be10318}" /v UpperFilters
```
4. `pnputil /enum-drivers` for the driver-store view; `setupapi.dev.log`
   (`C:\Windows\INF`) for the full install narrative.

## Related Entries
- V1.C3.E008 — ConfigManagerErrorCode table · V4.C2.E005 — driver rollbacks

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C12.E008
title: "CAPI2/Operational: Certificate Chain Failures"
category: event-id
event: { id: 30, provider: "Microsoft-Windows-CAPI2", channel: "Microsoft-Windows-CAPI2/Operational", level: Error }
severity_for_triage: medium
applies_to: ["Windows Vista+ — channel disabled by default"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
**Disabled by default — enable it, reproduce, read, disable.** CAPI2 logs
every certificate operation in forensic detail: `11` chain building, `30`
chain validation verdict, `41/42` revocation (CRL/OCSP) retrieval and
failures, `70` private-key access. Any mystery involving "certificate is not
trusted," TLS failures, code-signing rejections, or 802.1X cert problems
becomes legible here — the events carry the full chain, the exact failing
element, and the status.

## Meaning
Frequent verdicts decoded: `CERT_TRUST_REVOCATION_STATUS_UNKNOWN` = the
client couldn't *reach* CRL/OCSP endpoints (proxy/firewall — the cause behind
countless "slow app start" and service 7009 timeouts, since revocation checks
block); `CERT_TRUST_IS_UNTRUSTED_ROOT` = missing/unmanaged root (root store
drift on isolated machines); `CERT_TRUST_IS_NOT_TIME_VALID` = expired cert or
wrong system clock (pair with time events); partial chain = missing
intermediate (server misconfiguration).

## Diagnostic Procedure
1. **[MODIFIES SYSTEM]** Enable, sized generously:
```cmd
wevtutil sl Microsoft-Windows-CAPI2/Operational /e:true /ms:104857600
```
2. Reproduce the failure, then read verdicts:
```powershell
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-CAPI2/Operational'; Id=30,41,42} -MaxEvents 30 |
  Select-Object TimeCreated, Id, Message | Format-List
```
3. Disable when done (it is voluminous):
```cmd
wevtutil sl Microsoft-Windows-CAPI2/Operational /e:false
```
4. Companion checks: `certutil -verify -urlfetch <cert.cer>` performs the
   same chain+revocation walk interactively and prints each URL it tries.

## Related Entries
- V2.C3.E7009 — revocation-blocked service starts · V2.C12.E006 — 802.1X

## References & Attribution
- original synthesis — License: n/a
