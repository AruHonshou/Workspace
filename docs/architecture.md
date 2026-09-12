# AmeWork 2 architecture

AmeWork is a local-first React and FastAPI application. SQLite stores profiles,
confirmed evidence, searches, normalized jobs, favorites and generated documents.
The browser uses REST for commands and reads; no automation logs into a job portal
or submits an application.

## Active product flow

1. `/buscar` sends a role, country, publication window and selected portals to
   `JobSearchService`. A CV and an AI key are not required.
2. `TheirStackProvider` supplies portal listings and `BreteProvider` supplies the
   Costa Rican public-employment source. Providers fail independently.
3. Deterministic normalization, canonical URL selection and cross-source
   deduplication create stored jobs. Identical searches use a short-lived SQLite
   cache; additional pages are fetched only after an explicit click.
4. `/favoritos` stores a job locally. Its detail page may combine that job with a
   selected profile for gap analysis, interview preparation or an ATS résumé.
5. `DeepSeekProvider` performs schema-validated completions directly through the
   official API. Pydantic models and evidence validators reject unsupported
   personal claims before a document is rendered.
6. `/linkedin` extracts a user-provided LinkedIn PDF locally, runs deterministic
   checks, then optionally requests evidence-bound improvements from DeepSeek.

## Boundaries

- TheirStack receives only search criteria, never a CV.
- DeepSeek receives only the confirmed professional facts needed for an explicit
  AI operation; contact details and original documents stay local.
- Credentials live in the operating-system credential vault or a runtime secret,
  never in SQLite or browser storage.
- The 3D scene is presentation only. All product functions work without WebGL.

The public API is generated in `frontend/src/generated/openapi.json`. Historical
database fields are retained solely so existing installations can migrate without
losing data; they are not public AmeWork 2 routes.
