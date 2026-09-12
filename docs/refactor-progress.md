# AmeWork 2 refactor status

## Implemented

- Five independent React routes: `/buscar`, `/favoritos`, `/favoritos/:id`, `/mi-cv`, `/linkedin` and `/configuracion`, plus the home scene.
- Compact application shell; search, Favorites and LinkedIn no longer compete inside a dashboard modal.
- Profile-free job search with role, ISO country, today/7/30-day windows and source selection.
- TheirStack provider boundary with deliberate pagination, 30-minute persisted cache and no automatic retry of uncertain billable pages.
- Selected LinkedIn, Indeed, Computrabajo and Glassdoor domains are now sent to TheirStack before any billable result is revealed; a Brete-only search never calls the paid provider.
- Separate public Brete/ANE provider for Costa Rica, with partial-failure isolation.
- Canonical deduplication, source-link preservation and company/ATS/portal URL preference.
- Profile-free, idempotent saved jobs and full-page Favorite details.
- Favorite tools for evidence-first gap analysis, interview guide generation and reviewable ATS résumé generation.
- Confirmed `ProfileFact` ledger, language-aware résumés, redacted cloud preview and explicit consent.
- Deterministic LinkedIn PDF/text parser plus versioned, copy-ready DeepSeek proposals.
- Direct provider-neutral AI boundary and DeepSeek implementation with one HTTPS call and strict Pydantic validation.
- Legacy agent-framework, graph/replay/live modules and secondary paid-provider dependencies removed from the package and generated API contract. Active AI work now lives in explicit service operations rather than a graph module.
- LinkedIn imports can be reparsed locally after parser improvements, and the chosen output language is persisted in every generated version.
- Saved-job interview guides poll only the modern route and expose separate preview and download links after PDF validation.
- Obsolete frontend graph runtime, replay controls, generic approvals and event-stream client removed.
- Legacy workflow, ranking and application-tracking routes removed from the public AmeWork 2 API. Historical rows are preserved in an exportable archive rather than exposed through retired features. Active discovery is TheirStack plus Brete.
- The obsolete direct result-analysis endpoint and the retired multi-document application-package renderer have been removed; AI tools now exist only inside a saved job.
- Duplicate matching now normalizes common QA/SDET/developer title abbreviations and legal company suffixes while retaining every source link.
- Modern profile-free searches persist in their own `searches` table and use a dedicated `SearchRecord` contract without agent runtime state.
- Favorites and interview guides can now reference modern searches directly through the non-destructive v10 storage migration; the obsolete runs-only foreign key no longer breaks document generation.
- A complete local acceptance journey now covers CV import and confirmation, search, saved job, fit analysis, interview-guide PDF, evidence-checked ATS résumé approval, PDF/DOCX export and data backup without external calls or paid credits.
- Data export now includes modern saved jobs and searches alongside preserved legacy records.
- Atomic migrations 11/12 consolidate interview guides and ATS documents under saved jobs, archive retired records and remove active runs/events/approvals/application tables. Tests cover rollback, repeated startup and both profiles retaining their documents.
- Interrupted document generation becomes explicitly retryable after restart without automatic paid calls. Deleting a favorite is blocked while its guide or ATS document is being generated.
- Regeneration preserves previously generated PDF versions, including older guides created before version tracking.
- Deleting a profile or saved job also removes only its recorded PDF/DOCX files inside the configured artifact root; paths outside that root are ignored defensively.
- Updated English/Spanish README and generated OpenAPI TypeScript contracts.

## Deliberately deferred

- A packaged Tauri/Windows installer, explicitly deferred until the project owner authorizes that final phase. The local web product remains runnable through the supported scripts and Docker.
- Broader semantic duplicate matching beyond the conservative title/company/location rules. It remains intentionally deferred until a labeled golden set exists to prevent false merges.
- Additional country-specific public portals. TheirStack coverage works by selected country; Brete is the first independent local adapter.

No test or smoke run spends real TheirStack credits or sends professional data to DeepSeek.
