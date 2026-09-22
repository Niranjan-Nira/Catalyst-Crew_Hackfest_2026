# Volume VIII · Chapter 1 — Name Resolution

Half of "the network is down" is really "a name didn't resolve." Windows tries
several resolvers in a fixed order, and knowing that order — and which one
answered — is most of DNS troubleshooting.

---
entry_id: V8.C1.E001
title: "The Resolution Order: HOSTS, DNS Cache, DNS, LLMNR/NetBIOS, mDNS"
category: concept
severity_for_triage: informational
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
When Windows resolves a name it consults sources in order, and the *first*
answer wins — which is why a stale HOSTS entry or a poisoned cache beats a
correct DNS record every time. The order (roughly): the DNS client cache
(which pre-loads the HOSTS file), then DNS servers per interface, then
fallback multicast/broadcast resolvers (LLMNR — now deprecated/disabled in
hardened environments — mDNS, and legacy NetBIOS name resolution).

## Meaning — practical consequences
- A wrong answer that "shouldn't be possible" from DNS is often HOSTS or a
  cached negative/positive entry (E003).
- Names resolving *without a domain suffix* rely on the DNS suffix search list;
  short-name failures are frequently a missing suffix, not a DNS-server
  problem.
- LLMNR/NetBIOS fallback resolving internal names is both a convenience and a
  security concern (spoofing) — many baselines disable them, after which
  short-name resolution that *used* to work via broadcast now fails and needs
  proper DNS/suffixes.

## Diagnostic Procedure
1. See the effective client configuration incl. suffixes:
```powershell
Get-DnsClientGlobalSetting | Select-Object SuffixSearchList
Get-DnsClient | Select-Object InterfaceAlias, ConnectionSpecificSuffix
```
2. Check HOSTS when an answer is inexplicable:
```powershell
Get-Content $env:SystemRoot\System32\drivers\etc\hosts | Where-Object { $_ -and $_ -notmatch '^\s*#' }
```

## Related Entries
- V8.C1.E002 — querying DNS · V8.C1.E003 — cache pitfalls · V2.C5.E1014 — DNS timeouts

## References & Attribution
- MicrosoftDocs/windows-itpro-docs — DNS client behavior — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — first-answer-wins consequences — License: n/a

---
entry_id: V8.C1.E002
title: "Diagnosing DNS: nslookup vs. Resolve-DnsName, and Reading Failures"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 8+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
A crucial gotcha: **`nslookup` does not use the Windows resolver** — it talks
straight to a DNS server, bypassing the client cache, HOSTS, and suffix logic.
So `nslookup` succeeding while applications fail is *normal and diagnostic*: it
means DNS itself is fine and the problem is in the client resolution path
(cache, HOSTS, suffixes) that `Resolve-DnsName` (which uses the real client)
would reveal.

## Diagnostic Procedure
1. Compare the two deliberately:
```powershell
Resolve-DnsName host.corp.com        # uses the Windows client path (cache, suffixes)
nslookup host.corp.com 10.0.0.10     # bypasses the client, asks the server directly
```
   - Both succeed → resolution is healthy; look elsewhere (routing, service).
   - `nslookup` OK, `Resolve-DnsName` wrong/fails → client-path problem (cache
     E003, HOSTS, suffix, per-interface DNS).
   - Both fail → DNS server/record/network problem.
2. Target a specific record type / server:
```powershell
Resolve-DnsName _ldap._tcp.dc._msdcs.corp.com -Type SRV
Resolve-DnsName host.corp.com -Server 10.0.0.10 -Type A
```
3. Read the failure: NXDOMAIN (name truly doesn't exist), SERVFAIL (server
   error/DNSSEC/forwarder issue), timeout (server unreachable — pair with
   V2.C5.E1014).

## Related Entries
- V8.C1.E001 — the order · V8.C1.E003 — caching · V2.C5.E1014

## References & Attribution
- original synthesis — License: n/a

---
entry_id: V8.C1.E003
title: "DNS Cache and Negative Caching Pitfalls"
category: procedure
severity_for_triage: medium
applies_to: ["Windows 8+"]
sources: [{ repo: "community-knowledge", license: "n/a — original synthesis" }]
last_reviewed: 2026-08-30
  
status: draft
---

## Overview
The DNS Client service caches both answers *and failures*. **Negative caching**
— remembering that a name didn't resolve — is the cause of the classic "I fixed
the DNS record but the client still says it can't find it": the client is
honoring a cached NXDOMAIN until its TTL expires. A flush resolves it instantly
and confirms the diagnosis.

## Diagnostic Procedure
1. Inspect the live cache (including negative entries):
```powershell
Get-DnsClientCache | Select-Object Entry, RecordType, Status, TimeToLive |
  Sort-Object TimeToLive
```
   `Status` other than Success on an entry = a cached failure.
2. Flush and re-test:
```powershell
Clear-DnsClientCache
Resolve-DnsName the.fixed.name
```
   If it works immediately after a flush, negative caching was the whole
   problem — nothing else changed.
3. Persistent bad entries that survive flushes usually trace back to HOSTS
   (E001) or a per-interface DNS server still serving the old record.

## Related Entries
- V8.C1.E001 · V8.C1.E002

## References & Attribution
- original synthesis — License: n/a
