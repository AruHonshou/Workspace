# Contributing to Workspace

Workspace is a local career application built with React and FastAPI. Contributions should make job search, professional documents and application tracking clearer and more reliable.

## Before opening a pull request

1. Describe the problem and the affected module.
2. Use synthetic profiles, job listings and documents in fixtures and screenshots.
3. Run ./scripts/test.ps1 for backend/frontend tests, lint, type checks and build.
4. If an API contract changed, run ./scripts/generate-contracts.ps1 and include the generated files.
5. Run ./scripts/validate-assets.ps1 and ./scripts/scan-secrets.ps1.
6. Update the relevant documentation and describe what you verified.

Preserve routes, existing local data and the explicit consent required for AI operations. Tests must not spend real provider credits or send personal data to external services.

## Project boundaries

- Search works independently of CVs and DeepSeek.
- AI statements about a person must be backed by their confirmed evidence.
- The user submits applications and edits LinkedIn themselves.
- Credentials belong in the operating-system vault or runtime secret injection.
- Do not commit CVs, personal exports, API keys or local databases.

The landing uses procedural desk geometry and local SVG artwork. Record licenses and provenance for new visual resources in THIRD_PARTY_ASSETS.md and the asset manifest; preserve existing third-party notices.

Start with the [README](README.md) and [technical documentation](docs/README.md).
