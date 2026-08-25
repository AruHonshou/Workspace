# Getting started

[Español](getting-started.es.md)

## Requirements

- Windows 10/11, Python 3.12, and `uv`.
- Node.js and the pnpm version pinned in `package.json`.
- A funded DeepSeek API key for structured agent analysis.
- A TheirStack API key for primary Costa Rica search coverage.
- Tesseract only for OCR of scanned PDFs.

```powershell
Copy-Item .env.example .env
./scripts/bootstrap.ps1
./scripts/dev.ps1
```

Open `http://127.0.0.1:5173`. In **Settings**, paste each API key in its provider
card and select **Validate and save**. Keys are validated separately and stored
in Windows Credential Manager; they are never written to `.env`.

Import the Spanish and English résumés, review and confirm their facts, enter a role, and wait for the
first batch of up to 25 jobs to finish. **Load 25 more** requests and caches the
next page and may consume up to 25 TheirStack credits. Results can switch between
24 hours, 7 days, and 30 days without rerunning. **I'm interested** creates the
PDF guide.

Synthetic replay works without an API key or network and never contains real data.
