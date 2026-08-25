from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import Settings
from .credentials import CredentialStore, CredentialStoreUnavailable
from .ranking import deduplicate_jobs, normalize_job
from .schemas import JobRecord, SourceKind


class TheirStackError(RuntimeError):
    """A safe, provider-level error that never contains credentials or payloads."""


@dataclass(slots=True)
class TheirStackPage:
    jobs: list[JobRecord]
    page: int
    total_available: int | None
    can_load_more: bool


def _portal_label(value: str | None) -> str | None:
    if not value:
        return None
    hostname = (urlparse(value).hostname or "").casefold()
    hostname = hostname.removeprefix("www.")
    known = {
        "linkedin.com": "LinkedIn",
        "indeed.com": "Indeed",
        "glassdoor.com": "Glassdoor",
        "computrabajo.com": "Computrabajo",
        "greenhouse.io": "Greenhouse",
        "lever.co": "Lever",
        "ashbyhq.com": "Ashby",
        "myworkdayjobs.com": "Workday",
    }
    for domain, label in known.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            return label
    return hostname or None


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


def normalize_theirstack_job(item: dict[str, object]) -> JobRecord | None:
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
    job = normalize_job(
        source=SourceKind.THEIRSTACK,
        external_id=str(item.get("id") or item.get("job_id") or apply_url),
        title=str(item.get("job_title") or item.get("title") or ""),
        company=_company_name(item),
        description=description,
        location=str(
            item.get("location")
            or item.get("long_location")
            or item.get("short_location")
            or "Costa Rica"
        ),
        remote=_remote_value(item),
        url=apply_url,
        posted_at=str(date_posted),
        raw=item,
    )
    job.provider = "theirstack"
    job.source_portal = _portal_label(source_url or listed_url)
    job.source_url = source_url or listed_url
    job.final_url = final_url
    job.apply_url_type = "company" if final_url else "portal"
    job.verification_level = "authorized_feed"
    job.official_url_verified = True
    return job


class TheirStackClient:
    def __init__(self, settings: Settings, credential_store: CredentialStore):
        self.settings = settings
        self.credential_store = credential_store

    def configured(self) -> bool:
        try:
            return bool(self.credential_store.get())
        except CredentialStoreUnavailable:
            return False

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
            raise TheirStackError("TheirStack no respondió durante la validación") from exc
        if response.status_code in {401, 403}:
            raise TheirStackError("TheirStack rechazó la API key")
        if response.status_code == 402:
            raise TheirStackError("La cuenta de TheirStack no tiene créditos disponibles")
        if response.status_code == 404:
            raise TheirStackError(
                "TheirStack no reconoce el endpoint de validación; comprueba el servicio"
            )
        if response.status_code >= 400:
            raise TheirStackError("TheirStack no pudo validar la API key")
        try:
            payload = response.json()
        except ValueError as exc:
            raise TheirStackError("TheirStack devolvió una respuesta de validación inválida") from exc
        if not isinstance(payload, dict):
            return None
        credits = payload.get("api_credits")
        if isinstance(credits, bool):
            return None
        if isinstance(credits, int | float):
            return max(0, int(credits))
        return None

    async def search_page(
        self,
        *,
        role: str,
        aliases: list[str],
        page: int,
    ) -> TheirStackPage:
        try:
            api_key = self.credential_store.get()
        except CredentialStoreUnavailable as exc:
            raise TheirStackError("TheirStack no está configurado") from exc
        if not api_key:
            raise TheirStackError("TheirStack no está configurado")
        titles = list(dict.fromkeys([role, *aliases]))[:12]
        body = {
            "job_title_or": titles,
            "job_country_code_or": ["CR"],
            "posted_at_max_age_days": 30,
            "is_closed": False,
            "page": page,
            "limit": self.settings.theirstack_batch_size,
            "include_total_results": page == 0,
        }
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
            raise TheirStackError("TheirStack no respondió durante la búsqueda") from exc
        if response.status_code in {401, 403}:
            raise TheirStackError("La API key de TheirStack ya no es válida")
        if response.status_code == 402:
            raise TheirStackError("TheirStack no tiene créditos suficientes")
        if response.status_code == 429:
            raise TheirStackError("TheirStack alcanzó temporalmente su límite de solicitudes")
        if response.status_code >= 400:
            raise TheirStackError("TheirStack no pudo completar esta página")
        try:
            payload = response.json()
        except ValueError as exc:
            raise TheirStackError("TheirStack devolvió una página inválida") from exc
        items = payload.get("data", []) if isinstance(payload, dict) else []
        jobs = [job for item in items if isinstance(item, dict) if (job := normalize_theirstack_job(item))]
        jobs = deduplicate_jobs(jobs)
        total = payload.get("total_results") if isinstance(payload, dict) else None
        if total is None and isinstance(payload, dict) and isinstance(payload.get("metadata"), dict):
            total = payload["metadata"].get("total_results")
        total_available = int(total) if isinstance(total, int | float) else None
        batch_size = self.settings.theirstack_batch_size
        can_load_more = len(items) >= batch_size and (
            total_available is None or (page + 1) * batch_size < total_available
        )
        return TheirStackPage(
            jobs=jobs,
            page=page,
            total_available=total_available,
            can_load_more=can_load_more,
        )


__all__ = [
    "TheirStackClient",
    "TheirStackError",
    "TheirStackPage",
    "normalize_theirstack_job",
]
