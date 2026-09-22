# Volume VIII · Chapter 3 — Proxy, VPN, and Edge Cases

The failures that break *some* traffic for *some* processes — the hardest
network tickets because they defy "the network is up or down" logic.

---
entry_id: V8.C3.E001
title: "Proxy Layers: WinINET vs. WinHTTP vs. Per-App"
category: concept
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
Windows has **two independent proxy configurations**, and confusing them causes
the signature "it works in the browser but not for updates/services":
**WinINET** is the per-*user* proxy (browsers, user apps — the Settings/IE
proxy UI); **WinHTTP** is the system/service proxy (Windows Update's DO,
services running as SYSTEM, background components). Setting one does not set the
other. A service failing to reach the internet while the logged-in user browses
fine is almost always a missing WinHTTP proxy.

## Meaning
- User-context apps (browsers, most GUI apps) → WinINET (per-user, supports
  PAC/WPAD auto-config).
- SYSTEM/service context (WU/Delivery Optimization, CRL fetches, some agents)
  → WinHTTP; if unset, they try direct and fail behind a mandatory proxy —
  causing update `0x8024402C` and the CAPI2 revocation timeouts of V2.C12.E008.
- Modern nuance: some components honor WPAD/PAC, some only static proxy;
  authenticated proxies break SYSTEM-context traffic that can't supply user
  creds.

## Diagnostic Procedure
1. Read *both* proxies:
```cmd
netsh winhttp show proxy
```
```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' |
  Select-Object ProxyEnable, ProxyServer, AutoConfigURL
```
2. **[MODIFIES SYSTEM]** Set the system proxy for services (or import from the
   user config):
```cmd
netsh winhttp set proxy proxy-server="http://proxy:8080" bypass-list="*.corp.com;<local>"
:: or:
netsh winhttp import proxy source=ie
```
3. Test in the failing context: a SYSTEM-context probe (via `psexec -s`) tells
   you what services actually see, not what your user session sees.

## Related Entries
- V4.C2.E002 — 0x8024402C update errors · V2.C12.E008 — CRL/revocation timeouts

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — WinHTTP proxy — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — two-proxy signature — License: n/a

---
entry_id: V8.C3.E002
title: "VPN and Always On VPN Troubleshooting"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
VPN failures divide into *won't connect* (tunnel establishment: auth,
certificates, protocol) and *connects but routing/DNS is wrong* (split vs.
force tunnel, DNS resolution over the tunnel). Always On VPN (AOVPN) adds
device/user tunnel complexity and profile deployment as failure points. The
RAS/VPN events and `Get-VpnConnection` are the surface.

## Diagnostic Procedure
1. Connection profiles and state:
```powershell
Get-VpnConnection | Select-Object Name, ServerAddress, ConnectionStatus,
  TunnelType, AuthenticationMethod, SplitTunneling
Get-VpnConnection -AllUserConnection   # AOVPN device tunnels live here
```
2. Establishment failures — read the RAS error and events:
```powershell
Get-WinEvent -LogName 'Application' -MaxEvents 30 |
  Where-Object ProviderName -match 'RasClient' |
  Select-Object TimeCreated, Id, Message
```
   Common RAS errors: 809 (NAT/UDP ports blocked — IKEv2 needs 500/4500),
   812/691 (auth/policy), 13801/13806 (IKE certificate problems — machine cert
   missing/untrusted, ties to V8.C3.E003).
3. Connected-but-broken: check what the tunnel did to routing and DNS:
```powershell
Get-NetRoute -AddressFamily IPv4 | Where-Object RouteMetric -lt 10
Get-DnsClientNrptPolicy      # split-DNS rules for internal names over VPN
```
   Missing NRPT rules = internal names don't resolve over a split tunnel — a
   very common "VPN connects but nothing works" cause.

## Related Entries
- V8.C1.* — the DNS-over-VPN side · V8.C3.E003 — VPN cert failures

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V8.C3.E003
title: "TLS/SSL Inspection and Certificate-Trust Failures"
category: concept
severity_for_triage: medium
applies_to: ["Windows 10/11"]
sources:
  - repo: "community-knowledge"
    license: "n/a — original synthesis"
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
Enterprise **TLS inspection** (a proxy/firewall decrypting HTTPS) works by
presenting its own certificate in place of the real site's — which only works
if the inspection CA is trusted on the client. When it isn't (or an app pins
certificates), connections fail with trust errors that look like "the internet
is broken" but are really a certificate-chain problem. This is where Chapter
12's CAPI2 diagnostics (V2.C12.E008) meet networking.

## Meaning — the failure shapes
- **Missing inspection root:** the proxy's CA isn't in the client's Trusted
  Root store → every HTTPS site shows a trust error. Fix: deploy the CA
  (usually via GPO/Intune); confirm it's present.
- **Certificate pinning:** some apps (and many non-browser agents, installers,
  and update clients) refuse an unexpected CA even if trusted — they *pin* the
  real cert. TLS inspection breaks these by design; the fix is a bypass rule
  for those endpoints on the proxy.
- **Revocation reachability:** if inspection or firewall blocks CRL/OCSP, chain
  validation stalls or fails (`REVOCATION_STATUS_UNKNOWN`) — the CAPI2 signature
  from V2.C12.E008, and the hidden cause of slow app starts.

## Diagnostic Procedure
1. Verify a full chain the way Windows does, seeing each fetched URL:
```cmd
certutil -verify -urlfetch C:\Diag\site.cer
```
2. Confirm the inspection CA is trusted:
```powershell
Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -like '*YourProxyCA*'
```
3. Enable CAPI2 (V2.C12.E008) to read the exact chain verdict when an app
   reports a vague TLS error.
4. Pinned/failing endpoints: request a TLS-inspection bypass for those FQDNs.

## Related Entries
- V2.C12.E008 — CAPI2 chain diagnostics · V8.C3.E001 — proxy layers

## References & Attribution
- original synthesis — License: n/a
