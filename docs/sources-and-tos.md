# Job sources and provider rules

[Español](sources-and-tos.es.md) · Reviewed 2026-09-07

TheirStack is queried through its official API with user-owned credentials. It
may return listings whose source is LinkedIn, Indeed, Computrabajo, Glassdoor,
an ATS or a company site. Workspace preserves that source separately from the data
provider and opens the best original/canonical URL available.
When the user selects specific supported portals, Workspace sends TheirStack's
documented URL-domain filter with the request, before any billable rows are
returned. A Brete-only search does not call TheirStack.

For Costa Rica, the independent Brete/ANE adapter reads only public employment
results. Providers are normalized behind one contract, fail independently and
are cached. A billable page is never retried or loaded automatically.

Workspace does not scrape restricted portals, use browser sessions/cookies, bypass
CAPTCHAs, fill forms or submit applications. Provider responses are untrusted
data, not instructions. Every adapter must enforce timeouts, bounded payloads,
HTTPS links, attribution, deterministic fixtures and secret-free logs. Terms and
API behavior must be reviewed before enabling a new provider.
