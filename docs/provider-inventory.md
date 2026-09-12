# Provider inventory

| Provider | Purpose | Credential | Data shared |
| --- | --- | --- | --- |
| TheirStack | Portal job discovery and pagination | User-owned key | Role, country, date window and selected source domains |
| Brete / ANE Costa Rica | Costa Rican public-employment results | None | Search term and public page parameters |
| DeepSeek | Explicit gap, interview, ATS résumé and LinkedIn operations | User-owned key | Redacted confirmed facts and the relevant job/profile text |

LinkedIn, Indeed, Computrabajo and Glassdoor are displayed as job sources when
TheirStack returns them. AmeWork does not scrape them, reuse their sessions or
submit forms. Every release must preserve source attribution, canonical links,
credit transparency and independent provider failure handling.
