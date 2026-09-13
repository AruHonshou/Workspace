# Public contracts

The runtime OpenAPI document and Pydantic models are authoritative. Generate the
browser contract with `scripts/generate-contracts.ps1`.

The Workspace public surface contains health/session metadata, countries and
providers, DeepSeek and TheirStack settings, profiles and confirmed facts,
profile-free searches, saved jobs, guide/ATS tools, LinkedIn imports, document
downloads and local data export/deletion.

Important invariants:

- Search input is `query`, country, publication window, source portals and page.
- TheirStack is a data provider; LinkedIn, Indeed, Computrabajo and Glassdoor are
  source portals.
- Saved-job AI operations always require an explicit `profile_id`.
- Generated personal statements cite confirmed fact IDs. Empty or unknown
  evidence cannot enter an ATS résumé as personal experience.
- Credentials and contact details never appear in API responses, logs or files.
- Historical workflow rows may be present in the private `historical_records`
  archive after migration, but they are not public routes or active runtime
  state.

The optional `X-Session-Token` must be passed as a header, never in a URL.
