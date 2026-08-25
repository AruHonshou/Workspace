# Evaluation

[Español](evaluation.es.md)

Acceptance requires unit tests for connectors, 24 h/7 d/30 d boundaries,
deduplication, ranking, credentials, events, animation subclips, and PDF output;
integration with a fake DeepSeek server; and an E2E from résumé to interview guide.

CI never uses a real key. The live smoke test is opt-in and runs only after the
credential is entered in the UI. Tests verify that the key, contact details,
prompts, and reasoning never appear in the database, logs, SSE, checkpoints, or
documents.

Network fixtures cover pagination, compression, limits, `429`, timeouts, and
partial sources. No test automates LinkedIn, Indeed, Glassdoor, or Computrabajo.
