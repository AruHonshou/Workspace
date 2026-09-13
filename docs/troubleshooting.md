# Troubleshooting Workspace

[Español](troubleshooting.es.md)

## Search does not start

Choose a role, country, publication window and at least one source. Search does not require a CV or DeepSeek. Configure TheirStack for its selected portals; Brete/ANE is an independent source for Costa Rica.

Provider errors can indicate a rejected key, missing balance, rate limits or an unavailable service. Check Settings before retrying. Refreshing a paid page can consume credits.

## No jobs appear

Try a broader role or a different publication window: 24 hours, 7 days or 30 days. Check the selected portals and provider warnings. Coverage varies by country and source.

## A portal is missing

The source selector reflects supported mappings. Actual listings depend on TheirStack coverage or the independent public source. Workspace does not log into restricted portals or use your browser sessions.

## AI generation fails

Check the DeepSeek key, model access and balance in Settings. Select the correct professional profile, confirm the required résumé variant and review the displayed consent. A network or provider error does not mean your local CV was deleted.

## PDF import fails

Try an unencrypted PDF with selectable text. Scanned documents require the optional OCR path and its system dependencies; a text PDF is preferable. Check the file error rather than repeatedly submitting a corrupt file.

## Credential vault fails

The desktop runtime requires the platform's secure credential store. Headless containers can use DEEPSEEK_API_KEY / THEIRSTACK_API_KEY or mounted files configured through their corresponding _FILE variables. Runtime-injected keys are read-only in the UI.

## Local server or WebGL fails

Keep the development terminal open. If a port is occupied, stop the previous instance before starting another. The interface is at http://127.0.0.1:5173/ and the backend health check is at http://127.0.0.1:8765/health.

When WebGL is unavailable, the static desk fallback keeps the entry and application navigation available.

Run ./scripts/diagnose.ps1 for read-only diagnostics and ./scripts/test.ps1 for synthetic tests. Remove personal data and keys from any logs shared in a bug report.
