# Volume VIII · Chapter 2 — Connectivity and Transport

"No internet" is a stack of possible failures. This chapter walks the layers in
order so you find the *lowest* broken one instead of guessing at the top.

---
entry_id: V8.C2.E001
title: "The Connectivity Ladder: Link → IP → Gateway → DNS → Service"
category: procedure
severity_for_triage: high
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Network troubleshooting has a natural bottom-up order; test each rung and stop
at the first failure, because everything above a broken rung fails too. Testing
top-down ("ping google") tells you *something's* wrong; testing bottom-up tells
you *what*.

## Diagnostic Procedure
1. **Link** — is the interface up with a valid config?
```powershell
Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name, LinkSpeed
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress, PrefixOrigin
```
   A `169.254.x.x` (APIPA) address = no DHCP (V2.C5.E8015) — stop here.
2. **IP/Gateway** — can you reach the default gateway?
```powershell
$gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0').NextHop | Select-Object -First 1
Test-NetConnection $gw
```
   Gateway unreachable = local network/VLAN/switch problem — stop here.
3. **DNS** — resolution working? (Chapter 1's tests.)
4. **Service** — can you reach the actual target port?
```powershell
Test-NetConnection api.corp.com -Port 443
```
5. The one-shot config dump for the whole ladder: `ipconfig /all` +
   `Get-NetRoute`. Read APIPA/gateway/DNS from it before running any pings.

## Related Entries
- V2.C5.E8015 — DHCP/APIPA · V8.C1.* — the DNS rung · V8.C2.E002 — NCSI

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V8.C2.E002
title: "NCSI and the 'No Internet' / Captive Portal Logic"
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
The "No Internet access" indicator (and the taskbar globe) comes from **NCSI**
(Network Connectivity Status Indicator), which actively probes known Microsoft
endpoints to decide if a network has real internet. Crucially, NCSI's verdict
can be *wrong about your actual connectivity* — the probe can fail while apps
work fine (probe endpoint blocked), or succeed while a captive portal blocks
everything else.

## Meaning — the misleading cases
- **False "No Internet" with working apps:** NCSI's specific probe URLs/DNS are
  blocked by a proxy/firewall while real traffic flows — common in enterprises
  that filter or redirect the NCSI endpoints. The indicator is wrong; the
  network is fine.
- **Captive portal detection:** NCSI triggers the sign-in page on hotel/airport
  Wi-Fi by noticing the probe was redirected. Failure to detect = no portal
  popup; the fix is often re-triggering detection or opening the portal URL
  manually.
- **Enterprise tuning:** organizations sometimes point NCSI at internal
  endpoints; a broken internal NCSI target makes every machine claim "no
  internet."

## Diagnostic Procedure
1. Trust a real test over the indicator:
```powershell
Test-NetConnection www.msftconnecttest.com -Port 80
Test-NetConnection api.corp.com -Port 443     # what actually matters to the user
```
2. Inspect NCSI config if the indicator is estate-wide wrong:
   `HKLM\SOFTWARE\Policies\Microsoft\Windows\NetworkConnectivityStatusIndicator`
   and the active-probe settings.
3. Rule: never troubleshoot to satisfy the globe icon — troubleshoot the app
   the user actually needs.

## Related Entries
- V8.C2.E001 — the real ladder · V8.C3.E001 — proxy blocking probes

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — NCSI — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — false-verdict cases — License: n/a

---
entry_id: V8.C2.E003
title: "TCP Diagnostics: Test-NetConnection, Ports, and Path"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 8+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Reachability is a per-port question, not a per-host one: a host can answer ping
and refuse 443, or drop ping and serve 443. `Test-NetConnection -Port` tests
what actually matters; combined with route/trace it localizes *where* a path
breaks.

## Diagnostic Procedure
1. The definitive service test (TCP handshake to the real port):
```powershell
Test-NetConnection api.corp.com -Port 443 -InformationLevel Detailed
```
   `TcpTestSucceeded: True` = the port is open end-to-end; ICMP result is
   secondary (many hosts drop ping but serve the port).
2. Where does the path break:
```powershell
Test-NetConnection api.corp.com -TraceRoute
```
3. What's listening locally (the server side of "connection refused"):
```powershell
Get-NetTCPConnection -State Listen |
  Select-Object LocalAddress, LocalPort, OwningProcess |
  Sort-Object LocalPort
```
4. Interpretation: connection *refused* (fast) = something answered but no
   listener/blocked by local rule; *timeout* (slow) = dropped silently by a
   firewall or unreachable path. This refused-vs-timeout distinction points at
   local firewall vs. network path.

## Related Entries
- V6.C2.E002 — firewall as the blocker · V2.C5.E4227 — the port-exhaustion case

## References & Attribution
- original synthesis — License: n/a
