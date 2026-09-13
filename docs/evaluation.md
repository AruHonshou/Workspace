# Workspace validation

[Español](evaluation.es.md)

Run ./scripts/test.ps1 from the repository root. It validates assets, runs backend and frontend tests, checks Python lint and TypeScript, and builds the frontend. The -Quick flag skips Python lint and the frontend production build/lint steps.

The regression suite covers:

- Profiles, confirmation, language selection and professional evidence.
- Search providers, pagination, date windows, caching and deduplication.
- Saved jobs, application tracking and additional professional information.
- Gap analysis, interview guides, ATS documents and LinkedIn proposals.
- Database migrations and preservation of existing records.
- Credentials, input boundaries and public API contracts.
- Browser routes, navigation, document actions and preference migration.
- Procedural desk geometry, projection, interaction and offline assets.

Use synthetic profiles, PDFs and provider responses. Tests must not require real API keys, spend credits or send candidate records to third parties.

Document checks must verify readable text, usable links and evidence-backed claims. Do not impose one page count on all document types: a résumé and an interview guide have different purposes.

When changing rendering, inspect representative PDFs and responsive screens in addition to automated checks. The asset validator, secret scanner and generated API contract check are separate repository checks.
