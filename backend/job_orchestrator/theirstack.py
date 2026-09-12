from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from .config import Settings
from .connectors.providers import (
    ProviderCoverage,
    ProviderSearchPage,
    ProviderSearchQuery,
)
from .credentials import CredentialStore, CredentialStoreUnavailable
from .ranking import clean_text, normalize_job
from .schemas import ApplyUrlType, JobRecord, JobSourceEvidence, SourceKind


class TheirStackError(RuntimeError):
    """A safe, provider-level error that never contains credentials or payloads."""


COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")
PORTAL_DOMAINS = {
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
    "glassdoor.com": "Glassdoor",
    "computrabajo.com": "Computrabajo",
    "infojobs.net": "InfoJobs",
    "naukri.com": "Naukri",
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "ashbyhq.com": "Ashby",
    "myworkdayjobs.com": "Workday",
    "smartrecruiters.com": "SmartRecruiters",
    "workable.com": "Workable",
}
ATS_DOMAINS = {
    "ashbyhq.com",
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "workable.com",
}
SEARCH_PORTAL_DOMAINS = {
    "linkedin": ("linkedin.com",),
    "indeed": ("indeed.com",),
    "computrabajo": ("computrabajo.com",),
    "glassdoor": ("glassdoor.com",),
    "infojobs": ("infojobs.net",),
    "naukri": ("naukri.com",),
    "company": tuple(sorted(ATS_DOMAINS | {"smartrecruiters.com", "workable.com"})),
}


def _country_code(value: str) -> str:
    normalized = value.strip().upper()
    if not COUNTRY_CODE_RE.fullmatch(normalized):
        raise ValueError("country_code must be an ISO 3166-1 alpha-2 code")
    return normalized


def _portal_label(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    hostname = (urlparse(candidate).hostname or "").casefold().removeprefix("www.")
    if hostname:
        for domain, label in PORTAL_DOMAINS.items():
            if hostname == domain or hostname.endswith(f".{domain}"):
                return label
        return hostname
    folded = re.sub(r"[^a-z0-9]", "", candidate.casefold())
    for domain, label in PORTAL_DOMAINS.items():
        if domain.split(".", 1)[0] in folded:
            return label
    return clean_text(candidate) or None


def _apply_url_type(*, final_url: str | None) -> ApplyUrlType:
    """Classify a preferred final URL without overstating portal links.

    TheirStack separates the discovered portal URL from the final destination.
    A final destination can still be a recognized ATS rather than the employer's
    own website, so the distinction remains visible to the user.
    """

    if not final_url:
        return ApplyUrlType.PORTAL
    hostname = (urlparse(final_url).hostname or "").casefold().removeprefix("www.")
    if any(
        hostname == domain or hostname.endswith(f".{domain}") for domain in ATS_DOMAINS
    ):
        return ApplyUrlType.ATS
    if any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in PORTAL_DOMAINS
    ):
        return ApplyUrlType.PORTAL
    return ApplyUrlType.OFFICIAL


def _company_name(item: dict[str, object]) -> str:
    company = item.get("company") or item.get("company_name")
    if isinstance(company, str):
        return company
    company_object = item.get("company_object")
    if isinstance(company_object, dict):
        return str(company_object.get("name") or "")
    return ""


def _remote_value(item: dict[str, object]) -> bool | None:
    direct = item.get("remote")
    if isinstance(direct, bool):
        return direct
    values = item.get("workplace_types") or item.get("workplace_type")
    if isinstance(values, str):
        values = [values]
    if isinstance(values, list):
        normalized = {str(value).casefold().replace("-", "_") for value in values}
        if "remote" in normalized:
            return True
        if normalized & {"hybrid", "on_site", "onsite"}:
            return False
    return None


def _location(item: dict[str, object]) -> str:
    direct = (
        item.get("location") or item.get("long_location") or item.get("short_location")
    )
    if isinstance(direct, str) and direct.strip():
        return direct
    cities = item.get("cities")
    countries = item.get("countries")
    parts = [
        *(
            [str(item.get("city"))]
            if isinstance(item.get("city"), str) and str(item.get("city")).strip()
            else []
        ),
        *(
            [str(value) for value in cities if value]
            if isinstance(cities, list)
            else []
        ),
        *(
            [str(item.get("country"))]
            if isinstance(item.get("country"), str) and str(item.get("country")).strip()
            else []
        ),
        *(
            [str(value) for value in countries if value]
            if isinstance(countries, list)
            else []
        ),
    ]
    return ", ".join(dict.fromkeys(parts))


def normalize_theirstack_job(
    item: dict[str, object], *, search_country_code: str | None = None
) -> JobRecord | None:
    if item.get("closed_at") or item.get("is_closed") is True:
        return None
    source_url = str(item.get("source_url") or "").strip() or None
    final_url = str(item.get("final_url") or "").strip() or None
    listed_url = str(item.get("url") or "").strip() or None
    apply_url = final_url or listed_url or source_url
    date_posted = item.get("date_posted") or item.get("posted_at")
    description = str(item.get("description") or "").strip()
    if not apply_url or not date_posted or not description:
        return None

    raw = dict(item)
    if search_country_code:
        raw["_search_country_code"] = _country_code(search_country_code)
    scraping_source = item.get("scraping_source") or item.get("source")
    portal = _portal_label(
        str(scraping_source) if scraping_source else source_url or listed_url
    )
    raw["source_evidence"] = [
        {
            "provider": "theirstack",
            "source_portal": portal,
            "source_url": source_url or listed_url,
            "final_url": final_url,
            "apply_url_type": _apply_url_type(final_url=final_url),
            "external_id": str(item.get("id") or item.get("job_id") or apply_url),
        }
    ]

    job = normalize_job(
        source=SourceKind.THEIRSTACK,
        external_id=str(item.get("id") or item.get("job_id") or apply_url),
        title=str(item.get("job_title") or item.get("title") or ""),
        company=_company_name(item),
        description=description,
        location=_location(item),
        remote=_remote_value(item),
        url=apply_url,
        posted_at=str(date_posted),
        raw=raw,
    )
    apply_url_type = _apply_url_type(final_url=final_url)
    enriched = job.model_dump(mode="python")
    enriched.update(
        {
            "provider": "theirstack",
            "source_portal": portal,
            "source_url": source_url or listed_url,
            "final_url": final_url,
            "apply_url_type": apply_url_type,
            "source_evidence": [
                JobSourceEvidence(
                    provider="theirstack",
                    source_portal=portal,
                    source_url=source_url or listed_url,
                    final_url=final_url,
                    apply_url_type=apply_url_type,
                    external_id=job.external_id,
                ).model_dump(mode="python")
            ],
            "country_code": (
                _country_code(search_country_code)
                if search_country_code
                else job.country_code
            ),
            "verification_level": "authorized_feed",
            "official_url_verified": True,
        }
    )
    return JobRecord.model_validate(enriched)


def _workplace_types(modalities: tuple[str, ...]) -> list[str]:
    mapping = {
        "onsite": "on_site",
        "on_site": "on_site",
        "hybrid": "hybrid",
        "remote": "remote",
    }
    return list(
        dict.fromkeys(
            mapping[value.casefold()]
            for value in modalities
            if value.casefold() in mapping
        )
    )


def _source_domains(portals: tuple[str, ...]) -> list[str]:
    return list(
        dict.fromkeys(
            domain
            for portal in portals
            if portal.casefold() in SEARCH_PORTAL_DOMAINS
            for domain in SEARCH_PORTAL_DOMAINS[portal.casefold()]
        )
    )


class TheirStackClient:
    provider_id = "theirstack"
    billable_results = True

    def __init__(self, settings: Settings, credential_store: CredentialStore):
        self.settings = settings
        self.credential_store = credential_store

    def configured(self) -> bool:
        try:
            return bool(self.credential_store.get())
        except CredentialStoreUnavailable:
            return False

    def _api_key(self) -> str:
        try:
            api_key = self.credential_store.get()
        except CredentialStoreUnavailable as exc:
            raise TheirStackError("TheirStack no está configurado") from exc
        if not api_key:
            raise TheirStackError("TheirStack no está configurado")
        return api_key

    async def validate_key(self, api_key: str) -> int | None:
        """Validate a key without retrieving jobs or consuming result credits."""
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.theirstack_base_url,
                timeout=min(self.settings.request_timeout_seconds, 30),
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    "/v0/billing/credit-balance",
                    headers={"Authorization": f"Bearer {api_key.strip()}"},
                )
        except httpx.HTTPError as exc:
            raise TheirStackError(
                "TheirStack no respondió durante la validación"
            ) from exc
        self._raise_for_status(response, operation="validación")
        try:
            payload = response.json()
        except ValueError as exc:
            raise TheirStackError(
                "TheirStack devolvió una respuesta de validación inválida"
            ) from exc
        if not isinstance(payload, dict):
            return None
        credits = payload.get("api_credits")
        if isinstance(credits, bool):
            return None
        if isinstance(credits, int | float):
            return max(0, int(credits))
        return None

    @staticmethod
    def _raise_for_status(response: httpx.Response, *, operation: str) -> None:
        if response.status_code in {401, 403}:
            raise TheirStackError("TheirStack rechazó la API key")
        if response.status_code == 402:
            raise TheirStackError(
                "La cuenta de TheirStack no tiene créditos disponibles"
            )
        if response.status_code == 429:
            raise TheirStackError(
                "TheirStack alcanzó temporalmente su límite de solicitudes"
            )
        if response.status_code >= 400:
            raise TheirStackError(f"TheirStack no pudo completar la {operation}")

    def _search_body(
        self,
        query: ProviderSearchQuery,
        *,
        include_total_results: bool,
        coverage_only: bool = False,
    ) -> dict[str, object]:
        country_code = _country_code(query.country_code)
        titles = list(dict.fromkeys([query.role, *query.aliases]))[:12]
        body: dict[str, object] = {
            "job_title_or": titles,
            "job_country_code_or": [country_code],
            "posted_at_max_age_days": query.max_age_days,
            "is_closed": False,
            "page": query.page,
            "limit": 1 if coverage_only else query.page_size,
            "include_total_results": include_total_results,
        }
        workplace_types = _workplace_types(query.modalities)
        if workplace_types:
            body["workplace_types_or"] = workplace_types
        source_domains = _source_domains(query.portals)
        if source_domains:
            body["url_domain_or"] = source_domains
        if coverage_only:
            # This exact combination is TheirStack's documented Free Count
            # mode. If a workspace has not enabled it, estimate_coverage returns
            # unavailable and never retries with unblurred/billable data.
            body["blur_company_data"] = True
        return body

    async def _post(
        self, body: dict[str, object], *, operation: str
    ) -> dict[str, object]:
        api_key = self._api_key()
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.theirstack_base_url,
                timeout=min(self.settings.request_timeout_seconds, 45),
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    "/v1/jobs/search",
                    json=body,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
        except httpx.HTTPError as exc:
            raise TheirStackError(
                f"TheirStack no respondió durante la {operation}"
            ) from exc
        self._raise_for_status(response, operation=operation)
        try:
            payload = response.json()
        except ValueError as exc:
            raise TheirStackError("TheirStack devolvió una página inválida") from exc
        if not isinstance(payload, dict):
            raise TheirStackError("TheirStack devolvió una página inválida")
        return payload

    @staticmethod
    def _total(payload: dict[str, object]) -> int | None:
        total = payload.get("total_results")
        metadata = payload.get("metadata")
        if total is None and isinstance(metadata, dict):
            total = metadata.get("total_results")
        if isinstance(total, bool):
            return None
        return max(0, int(total)) if isinstance(total, int | float) else None

    async def estimate_coverage(self, query: ProviderSearchQuery) -> ProviderCoverage:
        if query.portals and not _source_domains(query.portals):
            return ProviderCoverage(
                provider=self.provider_id,
                country_code=_country_code(query.country_code),
                total_matches=0,
                available=False,
            )
        try:
            payload = await self._post(
                self._search_body(
                    query, include_total_results=True, coverage_only=True
                ),
                operation="consulta de cobertura",
            )
        except TheirStackError as exc:
            return ProviderCoverage(
                provider=self.provider_id,
                country_code=_country_code(query.country_code),
                total_matches=None,
                available=False,
                warning=str(exc),
            )
        return ProviderCoverage(
            provider=self.provider_id,
            country_code=_country_code(query.country_code),
            total_matches=self._total(payload),
            available=True,
            free_count_used=True,
        )

    async def search(self, query: ProviderSearchQuery) -> ProviderSearchPage:
        if query.page < 0:
            raise ValueError("page must be non-negative")
        if query.max_age_days not in (1, 7, 30):
            raise ValueError("Unsupported publication window")
        if not 1 <= query.page_size <= 25:
            raise ValueError("Page size must be between 1 and 25")
        if query.portals and not _source_domains(query.portals):
            return ProviderSearchPage(
                provider=self.provider_id,
                jobs=[],
                page=query.page,
                page_size=query.page_size,
                total_available=0,
                can_load_more=False,
            )
        payload = await self._post(
            self._search_body(query, include_total_results=query.page == 0),
            operation="búsqueda",
        )
        items = payload.get("data", [])
        if not isinstance(items, list):
            raise TheirStackError("TheirStack devolvió una página inválida")
        jobs = [
            job
            for item in items
            if isinstance(item, dict)
            if (
                job := normalize_theirstack_job(
                    item, search_country_code=query.country_code
                )
            )
        ]
        total_available = self._total(payload)
        can_load_more = len(items) >= query.page_size and (
            total_available is None
            or (query.page + 1) * query.page_size < total_available
        )
        return ProviderSearchPage(
            provider=self.provider_id,
            jobs=jobs,
            page=query.page,
            page_size=query.page_size,
            total_available=total_available,
            can_load_more=can_load_more,
        )

__all__ = [
    "TheirStackClient",
    "TheirStackError",
    "normalize_theirstack_job",
]
