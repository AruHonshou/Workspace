# Troubleshooting

[Español](troubleshooting.es.md)

## Search does not start

Confirm at least one résumé variant and choose a valid country and role. DeepSeek is not required for search. If a paid provider is not configured, fallback sources may still return a smaller set. Use the coverage check before spending credits.

Provider status codes are shown safely: `401/403` means a rejected key, `402` insufficient plan/credits, and `429` a temporary quota. A paid page is not automatically retried; press retry/load only after resolving the cause.

## No jobs appear

Try a broader role, remove the city filter or allow worldwide remote. New results require an exact publication time within seven days and a valid HTTPS link. Coverage varies by country and provider; the UI does not claim complete Internet coverage.

## A portal is missing

LinkedIn, Indeed, Glassdoor, Computrabajo, Naukri and similar boards are represented only through an authorized provider, official API/feed, or a user-supplied link. AmeWork does not scrape them directly or use logged-in browser sessions.

## Model feature is unavailable

Search and deterministic fit summaries still work. For deep analysis, ATS résumé, interview guide or LinkedIn optimization, validate DeepSeek, grant the displayed purpose-specific consent and ensure a confirmed résumé exists in the job language.

## Credential vault fails

Windows needs Credential Manager, macOS needs Keychain and Linux needs Secret Service/libsecret. Headless containers should inject `*_API_KEY` or mount a secret file and set `*_API_KEY_FILE`; runtime-injected secrets are read-only in the UI.

## Animation or WebGL fails

The app automatically switches to its static fallback. Update the graphics driver if desired; all forms remain usable without WebGL or animation.

Run `./scripts/diagnose.ps1`, `./scripts/test.ps1` and `./scripts/scan-secrets.ps1` for local diagnostics.
