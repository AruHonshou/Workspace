# Getting started

[Español](getting-started.es.md)

Requirements: Python 3.12 with `uv`, Node.js 22+, the pinned pnpm version and
PowerShell 7. Docker is an alternative.

```powershell
Copy-Item .env.example .env
./scripts/bootstrap.ps1
./scripts/dev.ps1
```

Open `http://127.0.0.1:5173` and enter Workspace. Search is immediately available:
choose a role, country, Today/7 days/30 days and the desired source portals.
TheirStack is optional but provides the broad portal coverage; Brete/ANE is
available for Costa Rica. Repeated equivalent searches use the local cache and
**Load more** is always a manual, credit-aware action.

Create and confirm a profile in **My CV** only when you want AI tools. Save an
interesting job, open its detail page and select gap analysis, interview guide or
ATS résumé. Configure DeepSeek first; contact details and original PDFs remain
local. Import a LinkedIn PDF from its own page to obtain copyable, evidence-bound
improvements. Workspace never submits an application or edits LinkedIn.
