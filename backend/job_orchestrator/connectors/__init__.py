from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod

import httpx

from ..ranking import clean_text, deduplicate_jobs, normalize_job
from ..schemas import JobRecord, SearchRequest, SourceKind


class ConnectorError(RuntimeError):
    pass


class JobConnector(ABC):
    source: SourceKind
    max_response_bytes = 5 * 1024 * 1024

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @abstractmethod
    async def search(self, request: SearchRequest) -> list[JobRecord]: ...

    def identifier(self, request: SearchRequest) -> str:
        value = request.source_identifiers.get(str(self.source), "").strip()
        if not value:
            raise ConnectorError(f"source_identifiers.{self.source} is required")
        return value

    async def get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
    ) -> httpx.Response:
        async with self.client.stream("GET", url, params=params) as response:
            if response.is_redirect:
                raise ConnectorError("Connector redirects are not followed")
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > self.max_response_bytes:
                    raise ConnectorError("Connector response exceeded 5 MB")
            decoded_headers = {
                key: value
                for key, value in response.headers.items()
                if key.casefold() not in {"content-encoding", "content-length"}
            }
            return httpx.Response(
                status_code=response.status_code,
                headers=decoded_headers,
                content=bytes(content),
                request=response.request,
            )


class GreenhouseConnector(JobConnector):
    source = SourceKind.GREENHOUSE

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        board = self.identifier(request)
        response = await self.get(
            f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
            params={"content": "true"},
        )
        response.raise_for_status()
        items = response.json().get("jobs", [])
        jobs = [
            normalize_job(
                source=self.source,
                external_id=str(item.get("id", "")),
                title=item.get("title", ""),
                company=board,
                description=item.get("content", ""),
                location=(item.get("location") or {}).get("name", ""),
                remote="remote" in ((item.get("location") or {}).get("name", "").casefold()),
                url=item.get("absolute_url"),
                # Greenhouse's public board payload exposes `updated_at`, not a
                # trustworthy first-publication timestamp. Keep it out of the
                # strict publication window instead of treating an edit
                # as a new vacancy.
                posted_at=None,
                raw=item,
            )
            for item in items
        ]
        return _filter(jobs, request)


class LeverConnector(JobConnector):
    source = SourceKind.LEVER

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        site = self.identifier(request)
        response = await self.get(
            f"https://api.lever.co/v0/postings/{site}", params={"mode": "json"}
        )
        response.raise_for_status()
        jobs = []
        for item in response.json():
            categories = item.get("categories") or {}
            description = "\n".join(
                filter(
                    None,
                    [
                        item.get("descriptionPlain"),
                        item.get("additionalPlain"),
                        *[section.get("content", "") for section in item.get("lists", [])],
                    ],
                )
            )
            location = categories.get("location", "")
            jobs.append(
                normalize_job(
                    source=self.source,
                    external_id=item.get("id", ""),
                    title=item.get("text", ""),
                    company=site,
                    description=description,
                    location=location,
                    remote="remote" in location.casefold(),
                    url=item.get("hostedUrl"),
                    raw=item,
                )
            )
        return _filter(jobs, request)


class AshbyConnector(JobConnector):
    source = SourceKind.ASHBY

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        board = self.identifier(request)
        response = await self.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
        response.raise_for_status()
        jobs = []
        for item in response.json().get("jobs", []):
            location = item.get("location", "")
            jobs.append(
                normalize_job(
                    source=self.source,
                    external_id=item.get("id") or item.get("jobUrl", ""),
                    title=item.get("title", ""),
                    company=board,
                    description=item.get("descriptionPlain") or item.get("descriptionHtml", ""),
                    location=location,
                    remote=item.get("isRemote") if "isRemote" in item else "remote" in location.casefold(),
                    url=item.get("jobUrl") or item.get("applyUrl"),
                    posted_at=item.get("publishedAt"),
                    raw=item,
                )
            )
        return _filter(jobs, request)


class HimalayasConnector(JobConnector):
    source = SourceKind.HIMALAYAS

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        response = await self.get(
            "https://himalayas.app/jobs/api",
            # When aliases are provided, fetch the recent catalogue and apply the
            # complete bilingual role expansion locally instead of asking the API
            # to match only the literal user input.
            params={"limit": min(request.limit, 100), "q": None if request.aliases else request.query or None},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("jobs", payload if isinstance(payload, list) else [])
        jobs = []
        for item in items:
            company_value = item.get("company", "")
            company = company_value.get("name", "") if isinstance(company_value, dict) else company_value
            jobs.append(
                normalize_job(
                    source=self.source,
                    external_id=str(item.get("id") or item.get("slug", "")),
                    title=item.get("title", ""),
                    company=company,
                    description=item.get("description", ""),
                    location=item.get("location", "Remote"),
                    remote=True,
                    url=item.get("applicationUrl") or item.get("url"),
                    # The strict career search accepts the explicit publication
                    # field only; creation/update metadata is not substituted.
                    posted_at=item.get("publishedAt"),
                    raw=item,
                )
            )
        return _filter(jobs, request)


class WeWorkRemotelyConnector(JobConnector):
    source = SourceKind.WWR

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        response = await self.get("https://weworkremotely.com/remote-jobs.rss")
        response.raise_for_status()
        root = ET.fromstring(response.text)
        jobs = []
        for item in root.findall(".//item"):
            title_value = item.findtext("title", "")
            company, _, title = title_value.partition(":")
            url = item.findtext("link", "")
            jobs.append(
                normalize_job(
                    source=self.source,
                    external_id=item.findtext("guid", url),
                    title=title or title_value,
                    company=company or "We Work Remotely",
                    description=item.findtext("description", ""),
                    location="Remote",
                    remote=True,
                    url=url,
                    posted_at=item.findtext("pubDate"),
                    raw={"title": title_value, "link": url},
                )
            )
        return _filter(jobs, request)


class JobicyConnector(JobConnector):
    source = SourceKind.JOBICY

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        response = await self.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": min(request.limit, 100)},
        )
        items = response.json().get("jobs", [])
        jobs = [
            normalize_job(
                source=self.source,
                external_id=str(item.get("id", "")),
                title=item.get("jobTitle", ""),
                company=item.get("companyName", ""),
                description=item.get("jobDescription", ""),
                location=item.get("jobGeo", "Remote"),
                remote=True,
                url=item.get("url"),
                posted_at=item.get("pubDate"),
                raw=item,
            )
            for item in items
            if isinstance(item, dict)
        ]
        return _filter(jobs, request)


class RemotiveConnector(JobConnector):
    source = SourceKind.REMOTIVE

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        response = await self.get("https://remotive.com/api/remote-jobs")
        items = response.json().get("jobs", [])
        jobs = [
            normalize_job(
                source=self.source,
                external_id=str(item.get("id", "")),
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                description=item.get("description", ""),
                location=item.get("candidate_required_location", "Remote"),
                remote=True,
                url=item.get("url"),
                posted_at=item.get("publication_date"),
                raw=item,
            )
            for item in items
            if isinstance(item, dict)
        ]
        return _filter(jobs, request)


class RemoteOkConnector(JobConnector):
    source = SourceKind.REMOTE_OK

    async def search(self, request: SearchRequest) -> list[JobRecord]:
        response = await self.get("https://remoteok.com/api")
        payload = response.json()
        items = payload[1:] if isinstance(payload, list) else []
        jobs = [
            normalize_job(
                source=self.source,
                external_id=str(item.get("id") or item.get("slug", "")),
                title=item.get("position", ""),
                company=item.get("company", ""),
                description=item.get("description", ""),
                location=item.get("location", "Remote"),
                remote=True,
                url=item.get("apply_url") or item.get("url"),
                posted_at=item.get("date"),
                raw=item,
            )
            for item in items
            if isinstance(item, dict) and (item.get("id") or item.get("slug"))
        ]
        return _filter(jobs, request)


def _filter(jobs: list[JobRecord], request: SearchRequest) -> list[JobRecord]:
    queries = [
        value
        for value in {
            clean_text(request.query).casefold(),
            *(clean_text(alias).casefold() for alias in request.aliases),
        }
        if value
    ]
    location = clean_text(request.location).casefold()
    filtered = []
    for job in jobs:
        title = clean_text(job.title).casefold()
        if queries and not any(
            re.search(rf"(?<!\w){re.escape(query)}(?!\w)", title)
            for query in queries
        ):
            continue
        if location and location not in job.location.casefold():
            continue
        if request.remote_only and job.remote is False:
            continue
        filtered.append(job)
    return deduplicate_jobs(filtered)[: request.limit]


CONNECTOR_TYPES: dict[SourceKind, type[JobConnector]] = {
    SourceKind.GREENHOUSE: GreenhouseConnector,
    SourceKind.LEVER: LeverConnector,
    SourceKind.ASHBY: AshbyConnector,
    SourceKind.HIMALAYAS: HimalayasConnector,
    SourceKind.WWR: WeWorkRemotelyConnector,
    SourceKind.JOBICY: JobicyConnector,
    SourceKind.REMOTIVE: RemotiveConnector,
    SourceKind.REMOTE_OK: RemoteOkConnector,
}


async def search_connectors(
    request: SearchRequest,
    *,
    timeout: float = 30.0,
) -> tuple[list[JobRecord], dict[str, str]]:
    jobs: list[JobRecord] = []
    errors: dict[str, str] = {}
    sources = [source for source in request.sources if source in CONNECTOR_TYPES]
    if not sources:
        return [], {"request": "Select at least one authorized network source"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        scheduled: list[tuple[SourceKind, asyncio.Task[list[JobRecord]]]] = []
        for source in sources:
            connector_type = CONNECTOR_TYPES.get(source)
            if connector_type is None:
                continue
            scheduled.append(
                (source, asyncio.create_task(connector_type(client).search(request)))
            )
        results = await asyncio.gather(
            *(task for _, task in scheduled), return_exceptions=True
        )
        for (source, _), result in zip(scheduled, results, strict=True):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, (ConnectorError, httpx.HTTPError, ValueError, ET.ParseError)):
                errors[str(source)] = str(result)
            elif isinstance(result, BaseException):
                errors[str(source)] = f"Unexpected connector failure: {type(result).__name__}"
            else:
                jobs.extend(result)
    return deduplicate_jobs(jobs)[: request.limit], errors


__all__ = [
    "AshbyConnector",
    "ConnectorError",
    "GreenhouseConnector",
    "HimalayasConnector",
    "JobConnector",
    "JobicyConnector",
    "LeverConnector",
    "RemoteOkConnector",
    "RemotiveConnector",
    "WeWorkRemotelyConnector",
    "search_connectors",
]
