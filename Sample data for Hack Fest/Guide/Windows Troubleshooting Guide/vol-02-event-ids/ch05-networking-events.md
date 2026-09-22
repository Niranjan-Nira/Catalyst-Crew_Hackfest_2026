# Volume II · Chapter 5 — System Log: Networking Events

These are the System-log networking signals; deep protocol channels
(DNS Client Events/Operational, DHCP-Client/Operational, SMBClient/
Connectivity, NCSI) add detail when the System-log summary isn't enough.
Domain-membership networking (Netlogon, time) continues in Chapter 6.

---
entry_id: V2.C5.E4227
title: "Tcpip 4227/4231: Ephemeral Port Exhaustion"
category: event-id
event: { id: 4227, provider: "Tcpip", channel: System, level: Warning }
severity_for_triage: high
applies_to: ["Windows 8+/Server 2012+"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`4231` — "A request to allocate an ephemeral port … has failed due to port
exhaustion" (with `4227` as the TCP-flavor warning) means outbound connections
are failing because the dynamic port range (default 49152–65535, ~16K ports)
is fully consumed. Symptom vocabulary users report: intermittent "connection
failures to everything" while existing connections keep working — a pattern
that misleads teams toward DNS or firewall hunts.

## Meaning
Two distinct mechanisms: **leak** (a process opens connections and never
closes — port count climbs and never falls) vs. **churn** (legitimate but
extreme connect/disconnect rate where TIME_WAIT sockets, held ~2×MSL, occupy
the range). The fix differs: leaks need the process fixed; churn needs
connection pooling or (carefully) range expansion.

## Likely Root Causes
1. **Leaking application/agent** — monitoring tools, custom apps, proxies with
   broken keep-alive. *very common*
2. **High-churn workloads** (web/API gateways, load tests) hitting TIME_WAIT
   accumulation. *common*
3. **WFP/AV filter drivers holding sockets.** *uncommon*

## Diagnostic Procedure
1. Confirm exhaustion and identify top consumers:
```powershell
Get-NetTCPConnection | Group-Object OwningProcess |
  Sort-Object Count -Descending | Select-Object -First 10 Count, Name |
  ForEach-Object { $_ | Add-Member -PassThru NoteProperty Proc ((Get-Process -Id $_.Name -ErrorAction SilentlyContinue).ProcessName) }
netstat -anob > C:\Diag\netstat.txt
```
2. Check the configured range and current TIME_WAIT weight:
```cmd
netsh int ipv4 show dynamicport tcp
```
```powershell
(Get-NetTCPConnection -State TimeWait).Count
```
3. Trend: sample the counts every few minutes — monotonic growth in one PID =
   leak; sawtooth tracking load = churn.
4. **[MODIFIES SYSTEM]** Mitigations while the root cause is fixed:
```cmd
netsh int ipv4 set dynamicport tcp start=10000 num=55535
```
   (Expand the range; do not shrink TIME_WAIT semantics casually — modern
   Windows already reuses aggressively.)

## Resolution
Leak: engage the owning process's vendor with the netstat evidence. Churn:
connection pooling/keep-alive at the application; range expansion as
headroom.

## Impact
On servers this is an availability incident with a deceptive signature —
"random" outbound failures — and it recurs on a timer as long as the leak
lives.

## Related Entries
- V1.C3.E003 — counters for trending · V2.C7 — pairing app evidence

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — port exhaustion troubleshooting — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — leak-vs-churn discrimination — License: n/a

---
entry_id: V2.C5.E5719
title: "NETLOGON 5719: No Domain Controller Available"
category: event-id
event: { id: 5719, provider: "NETLOGON", channel: System, level: Error }
severity_for_triage: medium
applies_to: ["domain-joined machines, all versions"]
sources:
  - repo: "MicrosoftDocs/SupportArticles-docs"
    license: "CC BY 4.0 (adapted)"
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`5719` — "This computer was not able to set up a secure session with a domain
controller in domain <X>…" — is the Netlogon service failing to reach/bind a
DC. Its single most important interpretive rule: **timing**. A 5719 in the
first seconds of boot, followed by successful domain activity, is the classic
race (NIC/switch port not ready before Netlogon starts) and is noise; 5719
recurring during steady state is a real reachability or DC-health problem.

## Likely Root Causes
1. **Boot-time race** — NIC driver init, spanning-tree convergence, 802.1X
   auth completing after Netlogon's first attempt. *very common, benign*
2. **DNS misconfiguration** — client pointing at non-domain DNS, missing SRV
   records. *very common when persistent*
3. **Network path** — VPN not up, firewall blocking DC ports, branch WAN.
   *common*
4. **DC-side trouble** — DC down/overloaded, site/subnet mapping sending
   clients to unreachable DCs. *common*

## Diagnostic Procedure
1. Classify by timestamp pattern first (boot-adjacent vs. steady-state):
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='NETLOGON'; Id=5719} -MaxEvents 20 |
  Select-Object TimeCreated, Message
```
2. Steady-state cases — test the discovery chain in order:
```cmd
nltest /dsgetdc:yourdomain.com
nslookup -type=SRV _ldap._tcp.dc._msdcs.yourdomain.com
nltest /sc_query:yourdomain.com
```
3. Verify the client's DNS servers are domain DNS and the machine's AD site
   mapping is sane (`nltest /dsgetsite`).
4. For boot-race cases that bother monitoring: fix at the network layer
   (portfast, 802.1X timing) rather than delaying Netlogon.

## Impact
Persistent 5719 degrades GP application, authentication fallback to cached
credentials (watch 4624 Type 11 spikes — V2.C9.E4624), and time sync — it is
upstream of half of Chapter 6's problems.

## Related Entries
- V2.C6.E1058 — GP's view of the same outage · V2.C6.E5722 — secure channel broken (different problem)

## References & Attribution
- MicrosoftDocs/SupportArticles-docs — Netlogon 5719 guidance — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — timing rule — License: n/a

---
entry_id: V2.C5.E1014
title: "DNS Client 1014: Name Resolution Timeout"
category: event-id
event: { id: 1014, provider: "Microsoft-Windows-DNS-Client", channel: System, level: Warning }
severity_for_triage: low
applies_to: ["Windows 7+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
`1014` — "Name resolution for the name <X> timed out after none of the
configured DNS servers responded" — is chronic low-level noise on most
machines (transient Wi-Fi gaps, sleeping, VPN transitions) and only
diagnostic in *aggregate*: which names, which times, how often.

## Meaning
Read the *name* in the event: timeouts for internal names only = internal DNS
servers/path; external names only = forwarder/ISP path; everything, clustered
at times = link drops (pair with WLAN 8003, V2.C12.E006) or VPN split-DNS
misrouting. Modern nuance: per-interface resolution and encrypted DNS (DoH)
policies can send different names to different servers — "which server was
asked" is no longer trivial.

## Diagnostic Procedure
1. Aggregate before theorizing:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-DNS-Client'; Id=1014} -MaxEvents 100 |
  Group-Object { ($_.Message -split '"')[1] } | Sort-Object Count -Descending | Select-Object -First 15 Count, Name
```
2. Live verification against each configured server:
```powershell
Get-DnsClientServerAddress -AddressFamily IPv4
Resolve-DnsName problematic.name -Server <each-server-ip>
```
3. Deep detail when needed: enable `Microsoft-Windows-DNS-Client/Operational`
   (per-query events, disabled by default) briefly.

## Related Entries
- V2.C12.E006 — link-drop correlation · V2.C5.E5719 — SRV-dependent failures

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C5.E10400
title: "NDIS and NIC Reset Events"
category: event-id
event: { id: 10400, provider: "Microsoft-Windows-NDIS", channel: System, level: Warning }
severity_for_triage: medium
applies_to: ["Windows 8+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The NIC layer narrates its instability across a small family: NDIS `10400`
("The network interface <X> has begun resetting… reset count <N>" — the
count is cumulative and the key trend number) and `10401/10402` (reset
complete/failed), plus per-vendor providers (e1dexpress/Intel, mlx, rtwlan)
logging link up/down. A resetting NIC produces the same user story as Wi-Fi
drops or port exhaustion — "network keeps blipping" — so this entry is the
tiebreaker.

## Meaning
Reset events name the *adapter*, and the embedded reset count tells you
whether this is the first or the five-hundredth. Recurring resets: driver/
firmware defects (dominant), power management (Selective Suspend / "allow the
computer to turn off this device"), thermal on high-throughput adapters, or
genuine hardware. A reset storm on a server NIC under load with a dated
driver is close to a signature.

## Diagnostic Procedure
1. Reset history and adapters involved:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-NDIS'} -MaxEvents 40 |
  Select-Object TimeCreated, Id, Message
```
2. Driver/firmware inventory for the adapter:
```powershell
Get-NetAdapter | Select-Object Name, InterfaceDescription, DriverVersion, DriverDate, Status, LinkSpeed
```
3. **[MODIFIES SYSTEM]** Rule out power management: NIC Properties → Power
   Management → untick "Allow the computer to turn off this device"; on
   servers also review Energy-Efficient Ethernet/Green settings in the
   advanced tab.
4. Update the NIC driver from the vendor (not just WU) and firmware where
   applicable; persistent resets after both = swap the port/adapter.

## Related Entries
- V2.C12.E006 — the Wi-Fi flavor · V2.C4.E011 — the storage analog of "blame the plumbing"

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V2.C5.E8015
title: "DHCP-Client Events: Conflicts, NACKs, and Lease Failures"
category: event-id
event: { id: 1002, provider: "Microsoft-Windows-Dhcp-Client", channel: System, level: Error }
severity_for_triage: medium
applies_to: ["Windows 7+"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The DHCP client's System-log vocabulary: `1002` — lease lost/denied ("The IP
address lease <IP> … has been denied by the DHCP server <IP> (NACK)"),
`1003/1001` — unable to contact a DHCP server (falls to APIPA 169.254.x.x),
`4198/4199` (address-conflict family: "the system detected an address
conflict for IP address <X> with the system having MAC address <Y>" — the
offender's MAC is *in the event*). Full transaction detail lives in
`Microsoft-Windows-Dhcp-Client/Operational` + `Admin`.

## Meaning
- NACK (1002) after a network move = normal (old lease on new segment); NACK
  storms on a stable network = server-side scope problems or rogue DHCP.
- APIPA fallback (1003 + 169.254 address) = the DISCOVER never got answered:
  path to the server (VLAN/relay/helper-address), server dead, or 802.1X
  gating the port until after timeout.
- Address conflict (4198/4199) = someone statically configured a leased IP —
  the embedded MAC identifies them; find the switch port by MAC.

## Diagnostic Procedure
1. Current state + quick discrimination:
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress, PrefixOrigin
ipconfig /all
```
   (`PrefixOrigin: WellKnown` + 169.254 = APIPA; `Dhcp` = leased.)
2. Event review incl. the conflict MAC:
```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Dhcp-Client'} -MaxEvents 30 |
  Select-Object TimeCreated, Id, Message
```
3. **[MODIFIES SYSTEM]** Controlled retry while watching the Operational
   channel:
```cmd
ipconfig /release & ipconfig /renew
```

## Related Entries
- V2.C5.E1014 — the next failure after bad addressing · V8.* — networking volume

## References & Attribution
- original synthesis — License: n/a
