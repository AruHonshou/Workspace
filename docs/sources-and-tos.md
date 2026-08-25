# Job sources and Terms of Service

[Español](sources-and-tos.es.md) · Last reviewed: 2026-08-20

AmeWork is a personal reader and decision tool, not a job-content
redistribution service. It stores provenance, links to the original posting,
uses conservative polling, and never submits an application.

## Primary source: TheirStack

TheirStack is queried through `POST /v1/jobs/search` for Costa Rica, open jobs,
and a maximum age of 30 days. The application requests 25 records per batch,
caches every page, and never automatically retries a billable page. Each returned
job may consume one credit. Provider, source portal, source URL, final URL, and
link type remain separate. See TheirStack documentation for
[sources](https://theirstack.com/en/docs/data/job/sources),
[credits](https://theirstack.com/en/docs/pricing/credits), and
[pagination](https://theirstack.com/en/docs/api-reference/pagination).

TheirStack may return listings originating on LinkedIn, Indeed, Glassdoor,
Computrabajo, ATSs, and company sites. That does not authorize this application
to automate those portals: it never uses their sessions, cookies, or HTML.

## Fallback connectors

| Connector | Authorized surface | Local policy |
| --- | --- | --- |
| Greenhouse | Public, unauthenticated Job Board `GET` endpoints documented by [Greenhouse](https://developers.greenhouse.io/job-board.html) | User configures an employer board token; cache and link to hosted application |
| Lever | Public postings `GET` endpoints in the official [Lever Postings API](https://github.com/lever/postings-api) | User configures a company site slug; never call the application `POST` endpoint |
| Ashby | Official [Public Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api) | User configures a job-board name; read published jobs only |
| Himalayas | Public [remote jobs API](https://himalayas.app/docs/remote-jobs-api) | Daily-scale refresh, handle `429`, preserve source attribution and application link |
| We Work Remotely | Public [RSS feeds](https://weworkremotely.com/remote-job-rss-feed) | Fetch the selected feed conservatively and retain attribution/backlink |
| Jobicy | Public [remote jobs feed/API](https://jobicy.com/jobs-rss-feed) | Maximum 100 records per response; preserve publication time and attribution |
| Remotive | Public [remote jobs API](https://github.com/remotive-io/remote-jobs-api) | Backlink attribution, cached catalogue, and no more frequent refresh than its published policy |
| Remote OK | Public [jobs API](https://remoteok.com/api) | Preserve attribution and the original application URL; cache the catalogue |
| Manual | URL, exact publication time, and text supplied by the user | No network request; visibly label imports from restricted portals |

GET access to an employer's public ATS board is not a blanket license to mirror
its database. Poll only user-selected boards, retain the minimum normalized
fields needed for the personal workflow, honor cache headers when available,
and delete expired local records according to user policy.

## Deferred optional sources

- [USAJOBS](https://developer.usajobs.gov/api-reference/get-api-search) is a
  legitimate official API when U.S. federal roles are relevant; it requires an
  API key and email/User-Agent identification.
- [Adzuna](https://developer.adzuna.com/docs/terms_of_service) requires an API
  key, attribution/backlink, and compliance with its quota and licensing terms.

They are not needed for a useful v1 and should not be enabled without a new
connector review and deterministic fixture.

## Prohibited direct automation

- [LinkedIn's User Agreement](https://www.linkedin.com/legal/user-agreement)
  prohibits scraping/crawlers and unauthorized automation. Its official
  [Job Posting API](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview?view=li-lts-2026-03)
  is a restricted partner publishing product, not a public job-search API.
- [Indeed's Terms](https://www.indeed.com/legal?hl=en_US) prohibit unauthorized
  scraping, agents, data mining, and bulk/automated applications. Its
  [Job Sync API](https://docs.indeed.com/job-sync-api) is for approved ATS
  partners posting jobs, not candidates searching them.
- [Glassdoor](https://www.glassdoor.com/about/terms/) restricts automated
  extraction without permission.
- [Computrabajo](https://co.computrabajo.com/avisolegal/) remains browser-only
  until an expressly authorized candidate-search integration is available.

Do not use browser cookies, extensions, unofficial APIs, search-result scraping,
CAPTCHA bypass, or a user's signed-in session. The UI opens equivalent searches
in a new browser tab; users then paste URL, exact publication time, and visible
text into the manual flow.

## Manual URL and email rules

For a pasted URL, recognize a known ATS and use its documented endpoint. For an
unknown site, ask the user to paste the visible description; do not turn a
single URL into a site crawler. If a page is fetched in a future opt-in feature,
enforce HTTPS, public-address DNS resolution, redirect limits, size/type limits,
robots/ToS review, and extraction of visible [`JobPosting`](https://schema.org/JobPosting)
structured data only.

Email ingestion in v1 means pasted text or a locally supplied `.eml`, not whole
mailbox OAuth. Gmail read scopes are [restricted scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
and can trigger verification/security obligations; Microsoft Graph's
[`Mail.Read`](https://learn.microsoft.com/en-us/graph/permissions-reference)
also grants broad mailbox access. Any future integration needs a separate data
flow and least-privilege review.

## Connector implementation checklist

- A unique source ID, canonical URL, retrieval timestamp, and content hash.
- Explicit connect/read timeouts, bounded response size, retries with backoff,
  and provider-specific rate limits.
- A truthful User-Agent/contact where a provider requires one.
- No secrets or raw provider payloads in SSE or normal logs.
- Sanitization before model use; external text is data, never instructions.
- Deterministic fixtures and replay that make zero network calls.
- Attribution in any UI view that displays provider content.
- Human navigation to the original application URL; no application `POST`.

Provider terms and APIs can change. A connector must fail closed when its
contract changes, and this review date must be updated after checking the linked
primary documentation.
