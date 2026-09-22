# Volume XI — Sources, Licensing & Attribution

## V11.C1.E001 — Source Registry

The encyclopedia draws on (and attributes to) these documentation lineages.
Content is **synthesized and rewritten**, never copied verbatim; the registry
exists so every generated record can name where its facts trace to.

| Source | What it covers | Typical license |
|---|---|---|
| `MicrosoftDocs/windows-itpro-docs` | Windows client IT-pro docs: deployment, configuration, security, client management | Docs: CC BY 4.0; code samples: MIT (verify per-repo LICENSE files) |
| `MicrosoftDocs/windowsserverdocs` | Windows Server administration and troubleshooting | CC BY 4.0 (docs) |
| `MicrosoftDocs/SupportArticles-docs` | Microsoft Support troubleshooting articles (Windows client/server, deployment, update) | CC BY 4.0 (docs) |
| `MicrosoftDocs/PowerShell-Docs` | Windows PowerShell / PowerShell 7 cmdlet and conceptual docs | CC BY 4.0 (docs), MIT (code) |
| `MicrosoftDocs/learn` | Microsoft Learn training modules and paths (much broader than Windows; use selectively) | CC BY 4.0 (docs) |
| `MicrosoftDocs/memdocs` | Intune / Configuration Manager (deployment & management volume) | CC BY 4.0 (docs) |
| `MicrosoftDocs/azure-docs` (Entra sections) | Hybrid join, device identity | CC BY 4.0 (docs) |
| Windows event-provider manifests | Authoritative message templates, compiled into Windows binaries (`.mui` message resources) | Facts extracted locally via `wevtutil`; not redistributable as files |
| Windows SDK headers (`ntstatus.h`, `winerror.h`) | Exception/NTSTATUS/HRESULT code names | Referenced, not reproduced |
| Community knowledge | Field-observed root-cause prevalence, triage heuristics | Original synthesis, marked as such |

**Important caveats**
1. Microsoft operates hundreds of public docs repositories; license terms are
   set **per repository**. Before ingesting any repo, read its `LICENSE` and
   `LICENSE-CODE` files and record the exact terms in this registry. Do not
   assume CC BY 4.0 — verify.
2. Event message templates compiled inside Windows binaries are not covered by
   docs licenses. This encyclopedia paraphrases message text and documents the
   local extraction method (`V2.C1.E004`) rather than redistributing manifests.
3. CC BY 4.0 permits sharing and adaptation with attribution; it does not grant
   trademark rights and must not imply Microsoft endorsement.

## V11.C1.E002 — License Retention Policy

- Every entry carries a `sources` block in front matter naming repo + license.
- When content is adapted from a CC BY 4.0 source: state the source, state the
  license, and note that the material was modified ("adapted from").
- Original analysis (root-cause prevalence rankings, triage heuristics) is
  labeled `original synthesis` so licensed and original material never blur.
- If a chunk aggregates entries with mixed sources, the zip includes this file
  so attribution travels with the content.

## V11.C1.E003 — Attribution Format for Generated Records

Machine-readable line format used in every entry's References section:

```
- <repo> — <path or article title> — License: <license> — retrieved <YYYY-MM-DD>
```

Example:

```
- MicrosoftDocs/windows-itpro-docs — client-management/troubleshoot-event-id-41-restart — License: CC BY 4.0 (adapted) — retrieved 2026-08-30
- original synthesis — root-cause prevalence ranking — License: n/a
```

## V11.C1.E004 — Curation Credit

This edition was curated and assembled by **Joe Prakash**. "Curated by" denotes
selection, structuring, synthesis, and original analysis across the eleven
volumes; it does not assert authorship of the underlying Microsoft
documentation, which remains under its respective repositories' licenses (see
V11.C1.E001–E003). Attribution to source repositories is retained per entry;
the curator credit sits alongside, not in place of, those attributions.
