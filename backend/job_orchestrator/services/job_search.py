from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from ..career import expand_role
from ..connectors.providers import JobSearchProvider, ProviderSearchQuery
from ..countries import normalize_country_code
from ..schemas import ApplyUrlType, JobRecord, SearchRecord, SearchStatus, utc_now
from ..storage import SQLiteStore
from ..theirstack import TheirStackError
from .job_identity import canonicalize_url, merge_jobs

Portal = Literal[
    "linkedin",
    "indeed",
    "computrabajo",
    "glassdoor",
    "infojobs",
    "naukri",
    "company",
    "brete",
]


class JobSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(min_length=2, max_length=120)
    country_code: str
    window_days: Literal[1, 7, 30] = 7
    portals: list[Portal] = Field(
        default_factory=lambda: ["linkedin", "indeed", "computrabajo", "glassdoor"],
        min_length=1,
    )
    request_id: UUID
    refresh: bool = False

    @field_validator("role")
    @classmethod
    def clean_role(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Enter a job title")
        return value

    @field_validator("country_code")
    @classmethod
    def country(cls, value: str) -> str:
        return normalize_country_code(value)

    def scope(self) -> dict:
        return {
            "role": self.role.casefold(),
            "country_code": self.country_code,
            "window_days": self.window_days,
            "portals": sorted(set(self.portals)),
        }


class SearchJob(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    description: str
    url: HttpUrl
    source_portal: str | None
    source_portals: list[str] = Field(default_factory=list)
    source_urls: list[HttpUrl] = Field(default_factory=list)
    apply_url_type: ApplyUrlType = ApplyUrlType.PORTAL
    published_at: datetime
    date_precision: Literal["day", "timestamp"]


class SearchResult(BaseModel):
    search_id: str
    status: str
    started_at: datetime
    jobs: list[SearchJob] = Field(default_factory=list)
    loaded_pages: list[int] = Field(default_factory=list)
    next_page: int | None = None
    excluded_count: int = 0
    cached: bool = False
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    total_available: int | None = None


class SearchConflict(RuntimeError):
    pass


class JobSearchService:
    """Explicit billable pages, persisted receipts, no profiles or AI calls.

    Search storage is isolated from document-operation runs. Pending page
    receipts survive restarts: uncertain requests must never be automatically
    sent again.
    """

    def __init__(self, store: SQLiteStore, provider: JobSearchProvider):
        self.store = store
        self.provider = provider
        self.lock = asyncio.Lock()
        with self.store.connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM searches WHERE status IN ('queued', 'running')"
            ).fetchall()
        for row in rows:
            interrupted = SearchRecord.model_validate_json(row["data_json"])
            interrupted.status = SearchStatus.FAILED
            interrupted.error = "La búsqueda fue interrumpida. Su consumo no se puede confirmar; no se reintentó."
            self.store.save_search(interrupted)

    def get(self, search_id: str, *, cached: bool = False) -> SearchResult:
        run = self.store.get_search(search_id)
        if run is None or run.request.get("flow") != "simple_search":
            raise KeyError(search_id)
        return SearchResult(
            search_id=run.search_id,
            status=run.status,
            started_at=run.created_at,
            cached=cached,
            jobs=run.result.get("jobs", []),
            loaded_pages=run.result.get("loaded_pages", []),
            next_page=run.result.get("next_page"),
            excluded_count=run.result.get("excluded_count", 0),
            error=run.error,
            warnings=run.result.get("warnings", []),
            total_available=run.result.get("total_available"),
        )

    async def search(self, query: JobSearchInput) -> SearchResult:
        async with self.lock:
            fingerprint = hashlib.sha256(
                json.dumps(query.scope(), sort_keys=True).encode()
            ).hexdigest()
            search_id = f"search_{query.request_id.hex}"
            existing = self.store.get_search(search_id)
            if existing:
                if existing.request.get("fingerprint") != fingerprint:
                    raise SearchConflict(
                        "This request identifier belongs to another search"
                    )
                return self.get(search_id, cached=True)
            # Query only this service's searches, without a global history limit.
            with self.store.connection() as connection:
                rows = connection.execute(
                    "SELECT data_json FROM searches ORDER BY created_at DESC"
                ).fetchall()
            for row in rows:
                previous = SearchRecord.model_validate_json(row["data_json"])
                if (
                    not query.refresh
                    and previous.request.get("fingerprint") == fingerprint
                    and previous.created_at >= utc_now() - timedelta(hours=24)
                ):
                    return self.get(previous.search_id, cached=True)
            run = SearchRecord(
                search_id=search_id,
                query=query.role,
                request={
                    "flow": "simple_search",
                    "fingerprint": fingerprint,
                    "payload": query.model_dump(mode="json"),
                },
            )
            self.store.save_search(run)
            await self._page(run, query, 0)
            return self.get(run.search_id)

    async def more(self, search_id: str, page: int) -> SearchResult:
        async with self.lock:
            self.get(search_id)
            run = self.store.get_search(search_id)
            assert run is not None
            if page in run.result.get("loaded_pages", []):
                return self.get(search_id, cached=True)
            if run.status != SearchStatus.COMPLETED or run.result.get("next_page") != page:
                raise SearchConflict(
                    "This page is unavailable or its previous request has an uncertain outcome. Start an explicit new search to retry."
                )
            await self._page(
                run, JobSearchInput.model_validate(run.request["payload"]), page
            )
            return self.get(search_id)

    async def _page(self, run: SearchRecord, query: JobSearchInput, page: int) -> None:
        run.status = SearchStatus.RUNNING
        run.result["pending_page"] = page
        self.store.save_search(run)
        try:
            result = await self.provider.search(
                ProviderSearchQuery(
                    role=query.role,
                    aliases=tuple(expand_role(query.role)[1:]),
                    country_code=query.country_code,
                    max_age_days=query.window_days,
                    portals=tuple(query.portals),
                    page_size=20,
                    page=page,
                )
            )
            previous_records = [
                stored
                for item in run.result.get("jobs", [])
                if (stored := self.store.get_job(item["job_id"])) is not None
            ]
            accepted_records = list(previous_records)
            excluded = int(run.result.get("excluded_count", 0))
            for job in result.jobs:
                if not self._accepted(job, query, run.created_at):
                    excluded += 1
                    continue
                self.store.save_job(job)
                accepted_records.append(job)
            jobs = []
            for canonical in merge_jobs(accepted_records):
                self.store.save_job(canonical.job)
                jobs.append(self._public(canonical.job).model_dump(mode="json"))
            run.result.update(
                jobs=jobs,
                loaded_pages=[*run.result.get("loaded_pages", []), page],
                excluded_count=excluded,
                next_page=page + 1 if result.can_load_more else None,
                warnings=list(
                    dict.fromkeys([*run.result.get("warnings", []), *result.warnings])
                ),
                total_available=result.total_available,
            )
            run.result.pop("pending_page", None)
            run.status = SearchStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001 -- persist a safe failure for all provider/parser/storage errors
            run.status = SearchStatus.FAILED
            run.error = (
                str(exc)
                if isinstance(exc, TheirStackError)
                else "No se pudo completar la página. No se reintentó automáticamente."
            )
        self.store.save_search(run)

    @staticmethod
    def _accepted(job: JobRecord, query: JobSearchInput, start: datetime) -> bool:
        if not job.url or job.url.scheme != "https" or not job.posted_at:
            return False
        source_portal = (job.source_portal or "").casefold()
        corporate_sources = {
            "greenhouse",
            "lever",
            "ashby",
            "workday",
            "smartrecruiters",
            "workable",
        }
        if source_portal not in query.portals and not (
            "company" in query.portals and source_portal in corporate_sources
        ):
            return False
        if job.country_code and job.country_code != query.country_code:
            return False
        raw_date = str(job.raw.get("date_posted") or job.raw.get("posted_at") or "")
        precision = "day" if len(raw_date) == 10 else "timestamp"
        posted = job.posted_at
        if posted.tzinfo is None:
            # Date-only values use a conservative UTC-day envelope; timestamps
            # without a timezone are ambiguous and cannot satisfy a strict filter.
            if precision != "day":
                return False
            posted = posted.replace(tzinfo=UTC)
        lower = start - timedelta(days=query.window_days)
        if precision == "day":
            if posted.date() <= lower.date() or posted.date() > start.date():
                return False
        elif not lower <= posted <= start:
            return False
        return True

    @classmethod
    def _accept(
        cls, job: JobRecord, query: JobSearchInput, start: datetime
    ) -> SearchJob | None:
        """Compatibility wrapper used by existing callers and boundary tests."""
        return cls._public(job) if cls._accepted(job, query, start) else None

    @staticmethod
    def _public(job: JobRecord) -> SearchJob:
        raw_date = str(job.raw.get("date_posted") or job.raw.get("posted_at") or "")
        precision = "day" if len(raw_date) == 10 else "timestamp"
        posted = job.posted_at
        assert job.url is not None and posted is not None
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=UTC)
        portals = list(
            dict.fromkeys(
                item.source_portal for item in job.source_evidence if item.source_portal
            )
        )
        urls = list(
            dict.fromkeys(
                url
                for item in job.source_evidence
                for url in (
                    canonicalize_url(item.final_url),
                    canonicalize_url(item.source_url),
                )
                if url
            )
        )
        return SearchJob(
            job_id=job.job_id,
            title=job.title,
            company=job.company,
            location=job.location,
            description=job.description,
            url=job.url,
            source_portal=job.source_portal,
            source_portals=portals,
            source_urls=urls,
            apply_url_type=job.apply_url_type,
            published_at=posted,
            date_precision=precision,
        )
