from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import urlencode

import httpx

from ...connectors.providers import (
    ProviderCoverage,
    ProviderSearchPage,
    ProviderSearchQuery,
)
from ...ranking import normalize_job
from ...schemas import ApplyUrlType, JobSourceEvidence, SourceKind


class BreteProvider:
    """Read public vacancy cards from Costa Rica's official ANE/Brete site.

    Brete does not expose a documented public jobs API.  This adapter therefore
    reads only the public search pages, sends no login/session data, uses a short
    timeout and never tries to bypass access controls.  The result always links
    back to the official search page.
    """

    provider_id = "brete"
    billable_results = False
    base_url = "https://ane.cr"
    _fallback_terms: ClassVar[dict[str, str]] = {
        "qa": "calidad",
        "quality assurance": "calidad",
    }
    _months: ClassVar[dict[str, int]] = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    def configured(self) -> bool:
        return True

    async def estimate_coverage(self, query: ProviderSearchQuery) -> ProviderCoverage:
        return ProviderCoverage(
            provider=self.provider_id,
            country_code=query.country_code,
            total_matches=None,
            available=query.country_code == "CR",
            warning=None
            if query.country_code == "CR"
            else "Brete sólo publica vacantes de Costa Rica.",
        )

    @staticmethod
    def _text(value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", " ", value)
        return " ".join(html.unescape(without_tags).split())

    @staticmethod
    def _fold(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return "".join(
            char for char in normalized if not unicodedata.combining(char)
        ).casefold()

    async def _occupation(self, client: httpx.AsyncClient, role: str) -> str | None:
        keyword = self._fallback_terms.get(self._fold(role), role)
        response = await client.post(
            "/Puesto/AutoCompleteEmpleos", data={"KeyWord": keyword}
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return None
        values = [
            str(item.get("DESCRIPCION", "")).strip()
            for item in payload
            if isinstance(item, dict)
        ]
        values = [value for value in values if value]
        if not values:
            return None
        needle = self._fold(keyword)
        return min(
            values, key=lambda value: (needle not in self._fold(value), len(value))
        )

    @classmethod
    def _date(cls, value: str) -> datetime | None:
        match = re.search(
            r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+del?\s+(\d{4})", value.casefold()
        )
        if not match:
            return None
        month = cls._months.get(cls._fold(match.group(2)))
        if month is None:
            return None
        return datetime(int(match.group(3)), month, int(match.group(1)), tzinfo=UTC)

    def _parse(self, content: str, source_url: str) -> list:
        cards = re.findall(
            r'<div class="job-listing">(.*?)(?=<div class="job-listing">|<div class="clearfix">\s*</div>\s*<div class="pagination-container|$)',
            content,
            re.DOTALL | re.IGNORECASE,
        )
        jobs = []
        for card in cards:
            company = re.search(
                r"job-listing-company[^>]*>(.*?)</h4>", card, re.DOTALL | re.IGNORECASE
            )
            title = re.search(
                r"job-listing-title[^>]*>(.*?)</h3>", card, re.DOTALL | re.IGNORECASE
            )
            descriptions = re.findall(
                r'<h4 class="job-listing-description">(.*?)</h4>',
                card,
                re.DOTALL | re.IGNORECASE,
            )
            published = re.search(
                r"Publicado el\s+(.*?)</small>", card, re.DOTALL | re.IGNORECASE
            )
            locations = re.findall(
                r"icon-material-outline-add-location[^>]*></i>\s*(.*?)</li>",
                card,
                re.DOTALL | re.IGNORECASE,
            )
            if not company or not title or not published:
                continue
            posted = self._date(self._text(published.group(1)))
            if posted is None:
                continue
            clean_title = self._text(title.group(1))
            clean_company = self._text(company.group(1))
            occupation = self._text(descriptions[0]) if descriptions else clean_title
            location = " · ".join(
                self._text(value) for value in locations if self._text(value)
            )
            identity = hashlib.sha256(
                f"{clean_company}|{clean_title}|{location}|{posted.date()}".encode()
            ).hexdigest()[:24]
            raw = {"date_posted": posted.date().isoformat(), "public_listing": True}
            job = normalize_job(
                source=SourceKind.BRETE,
                external_id=f"brete-{identity}",
                title=clean_title,
                company=clean_company,
                description=f"Clasificación ocupacional publicada por Brete: {occupation}.",
                location=location or "Costa Rica",
                remote=None,
                url=source_url,
                posted_at=posted,
                raw=raw,
            )
            job.provider = "brete"
            job.country_code = "CR"
            job.source_portal = "Brete"
            job.source_url = source_url
            job.apply_url_type = ApplyUrlType.PORTAL
            job.verification_level = "official"
            job.official_url_verified = True
            job.source_evidence = [
                JobSourceEvidence(
                    provider="brete",
                    source_portal="Brete",
                    source_url=source_url,
                    apply_url_type=ApplyUrlType.PORTAL,
                    external_id=job.external_id,
                )
            ]
            jobs.append(job)
        return jobs

    async def search(self, query: ProviderSearchQuery) -> ProviderSearchPage:
        if query.country_code != "CR" or (
            query.portals and "brete" not in query.portals
        ):
            return ProviderSearchPage(
                provider=self.provider_id,
                jobs=[],
                page=query.page,
                page_size=query.page_size,
                total_available=0,
                can_load_more=False,
            )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=20,
                follow_redirects=False,
                headers={"User-Agent": "Workspace/2.0 (+local personal job search)"},
            ) as client:
                occupation = await self._occupation(client, query.role)
                if not occupation:
                    return ProviderSearchPage(
                        provider=self.provider_id,
                        jobs=[],
                        page=query.page,
                        page_size=query.page_size,
                        total_available=0,
                        can_load_more=False,
                    )
                path = "/Puesto?" + urlencode(
                    {"Empleos": occupation, "Pagina": query.page + 1}
                )
                response = await client.get(path)
                response.raise_for_status()
                source_url = f"{self.base_url}{path}"
                jobs = self._parse(response.text, source_url)
                total_match = re.search(
                    r"Resultados encontrados:\s*(\d+)", response.text
                )
                total = int(total_match.group(1)) if total_match else None
                return ProviderSearchPage(
                    provider=self.provider_id,
                    jobs=jobs[: query.page_size],
                    page=query.page,
                    page_size=query.page_size,
                    total_available=total,
                    can_load_more=bool(
                        total and (query.page + 1) * query.page_size < total
                    ),
                )
        except (httpx.HTTPError, ValueError):
            return ProviderSearchPage(
                provider=self.provider_id,
                jobs=[],
                page=query.page,
                page_size=query.page_size,
                total_available=None,
                can_load_more=False,
                warnings=[
                    "Brete no respondió; los demás resultados siguen disponibles."
                ],
            )
