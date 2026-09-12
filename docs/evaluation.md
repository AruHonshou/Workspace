# Evaluation

[Español](evaluation.es.md)

Acceptance requires unit tests for multiple profiles, language-specific résumé
selection, the safe filter, connectors, 24 h/7 d/30 d boundaries, deduplication,
ranking, credentials, events, audio, and PDF output; integration with a fake
DeepSeek server; and an E2E from résumé to a versioned interview guide.

Spanish and English synthetic PDFs are text-extracted and rendered page by
page. They must contain 8 to 20 pages, selectable text, a clickable link,
Unicode fonts, no blank page, and no reference to an unconfirmed fact.

CI never uses a real key. The live smoke test is opt-in and runs only after the
credential is entered in the UI. Tests verify that the key, contact details,
prompts, and reasoning never appear in the database, logs, API responses, or
documents.

Network fixtures cover pagination, compression, limits, `429`, timeouts, and
partial sources. No test automates LinkedIn, Indeed, Glassdoor, or Computrabajo.
