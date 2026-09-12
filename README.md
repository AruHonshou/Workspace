# AmeWork 2

> A local-first, open-source workspace to find recent jobs, save useful opportunities, and prepare evidence-grounded applications without applying automatically.

[Español](README.es.md) · [Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](backend/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](backend/job_orchestrator/main.py)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=10202A)](frontend/package.json)
[![License: Apache 2.0](https://img.shields.io/badge/Code-Apache--2.0-D22128)](LICENSE)

![AmeWork home with Ame's animated terrarium](docs/images/amework-home.png)

## The product

AmeWork has five focused pages:

- **Search** — enter a role, country, publication window (today, 7 days or 30 days), and desired portals. Search does not require a résumé or AI.
- **Favorites** — keep interesting vacancies, open their original listing and, only when requested, analyze gaps, prepare an interview guide or create an ATS résumé.
- **My résumé** — create professional profiles, import language-specific résumés, review extracted facts and confirm the evidence ledger.
- **LinkedIn** — import LinkedIn's PDF export or pasted text and generate six copy-ready sections using the selected confirmed profile.
- **Settings** — configure TheirStack and DeepSeek in the operating-system credential vault, export local data or erase it.

AmeWork never logs into a job board, fills forms, sends email or submits an application.

## Search architecture

`JobSearchService` accepts only role, country, publication window, portals and an idempotency identifier. It has no dependency on profiles or AI.

- **TheirStack** is the optional BYOK data provider for records originating from LinkedIn, Indeed, Computrabajo, Glassdoor, company pages and ATSs, subject to actual coverage.
- **Brete/ANE** is an independent Costa Rica-only adapter that reads public official search cards without credentials or access-control bypasses.
- Every record keeps data provider and publication source separate.
- Duplicate listings are merged while preserving all observed source links. Preferred link order is company, ATS, then portal.
- Pages are requested manually, cached locally for 30 minutes and never retried automatically when a billable outcome is uncertain.
- AmeWork reports recovered sources and partial failures; it never claims to cover the whole Internet.

Restricted portals are not scraped directly. TheirStack's API is the data contract when a record originated on those portals.

## Evidence-grounded assistance

Optional AI features use one direct DeepSeek HTTPS request with strict Pydantic output validation. There is no agent framework or hidden tool loop.

The deterministic `ProfileFact` ledger is the authority. Generated personal claims must cite confirmed record identifiers; unsupported résumé lines are rejected in code. Reference answers in interview guides are educational content and are never presented as the user's experience.

The ATS flow is explicit:

1. Generate a one-column proposal in the vacancy language.
2. Validate every proposed line against confirmed evidence.
3. Show the draft and validation issues.
4. Require human approval.
5. Render selectable-text PDF and DOCX files.

LinkedIn follows the same boundary: deterministic PDF/text parsing first, then an optional evidence-checked proposal for headline, About, experience, education, skills and certifications.

## Privacy and security

- Résumés, extracted facts, jobs, favorites, analyses and generated files remain on the local machine.
- Search providers receive search criteria only, never résumé content.
- DeepSeek receives the minimum redacted, confirmed professional facts and required job/profile text only after a preview and consent.
- Original PDFs and contact details are not sent to DeepSeek.
- API keys live in Windows Credential Manager, macOS Keychain or Linux Secret Service (or runtime secret files); they never return to the browser, SQLite, events or documents.
- External job and PDF text is always treated as untrusted data.

## Run locally

Requirements: Python 3.12, `uv`, Node.js 22+, `pnpm` 11.19.0 and PowerShell 7. OCR is optional.

```powershell
git clone https://github.com/AruHonshou/AmeWork.git
cd AmeWork
Copy-Item .env.example .env
./scripts/bootstrap.ps1
./scripts/dev.ps1
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The API binds to `127.0.0.1:8765` by default. Docker development is available with `docker compose up --build`.

Runtime secrets are `THEIRSTACK_API_KEY` and `DEEPSEEK_API_KEY`, or their `_FILE` counterparts.

## Quality checks

```powershell
./scripts/test.ps1
./scripts/generate-contracts.ps1
./scripts/validate-assets.ps1
./scripts/scan-secrets.ps1
./scripts/generate-sbom.ps1
```

Tests use fake providers and synthetic profiles; they do not consume real API credits. OpenAPI generates the frontend TypeScript contract.

## Repository map

```text
backend/job_orchestrator/
  providers/jobs/       TheirStack boundary and Brete adapter
  providers/ai/         generic AIProvider and direct DeepSeek implementation
  services/             search identity, cache and explicit services
  documents/            evidence checks and deterministic renderers
frontend/src/
  app/                   routes and full-page layout
  pages/                 Search, Favorites and Favorite detail
  components/            résumé, LinkedIn, settings and 3D scene
assets/                  checksums and third-party provenance
```

## License and fan-work notice

Code is [Apache-2.0](LICENSE). Third-party media keeps its original license and attribution in [THIRD_PARTY_ASSETS.md](THIRD_PARTY_ASSETS.md) and [`assets/manifest.json`](assets/manifest.json).

**Smol Ame in an Upcycled Terrarium** is by **Seafoam**, licensed CC BY 4.0. AmeWork is an unofficial fan project and is not affiliated with or endorsed by COVER Corporation or hololive production.
