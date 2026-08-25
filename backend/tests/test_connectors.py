from __future__ import annotations

import httpx
import pytest

from job_orchestrator.connectors import (
    CONNECTOR_TYPES,
    ConnectorError,
    HimalayasConnector,
    JobicyConnector,
    RemoteOkConnector,
    RemotiveConnector,
    search_connectors,
)
from job_orchestrator.schemas import SearchRequest, SourceKind


@pytest.mark.asyncio
async def test_empty_source_selection_never_opens_the_network() -> None:
    jobs, errors = await search_connectors(SearchRequest(query="python"))

    assert jobs == []
    assert errors == {"request": "Select at least one authorized network source"}


@pytest.mark.asyncio
async def test_connector_rejects_redirects() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"location": "https://example.invalid/untrusted"},
            request=request,
        )
    )
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        connector = HimalayasConnector(client)
        with pytest.raises(ConnectorError, match="redirects are not followed"):
            await connector.get("https://himalayas.app/jobs/api")


@pytest.mark.asyncio
async def test_connector_caps_streamed_response_size() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"123456789", request=request)
    )
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        connector = HimalayasConnector(client)
        connector.max_response_bytes = 8
        with pytest.raises(ConnectorError, match="response exceeded"):
            await connector.get("https://himalayas.app/jobs/api")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("connector_type", "payload", "expected_source"),
    [
        (
            JobicyConnector,
            {"jobs": [{"id": 1, "jobTitle": "QA Engineer", "companyName": "Jobicy Co", "jobDescription": "QA automation", "jobGeo": "LATAM", "url": "https://jobs.example/jobicy", "pubDate": "2026-08-20T12:00:00Z"}]},
            SourceKind.JOBICY,
        ),
        (
            RemotiveConnector,
            {"jobs": [{"id": 2, "title": "QA Analyst", "company_name": "Remotive Co", "description": "QA testing", "candidate_required_location": "Worldwide", "url": "https://jobs.example/remotive", "publication_date": "2026-08-20T12:00:00Z"}]},
            SourceKind.REMOTIVE,
        ),
        (
            RemoteOkConnector,
            [{"legal": "metadata"}, {"id": 3, "position": "QA Tester", "company": "Remote Co", "description": "QA testing", "location": "Worldwide", "apply_url": "https://jobs.example/remote-ok", "date": "2026-08-20T12:00:00Z"}],
            SourceKind.REMOTE_OK,
        ),
    ],
)
async def test_public_remote_connectors_normalize_attribution(
    connector_type, payload, expected_source
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload, request=request)
    )
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        jobs = await connector_type(client).search(
            SearchRequest(query="QA", aliases=["QA"], limit=100)
        )

    assert len(jobs) == 1
    assert jobs[0].source == expected_source
    assert jobs[0].sources == [expected_source]
    assert jobs[0].verification_level == "authorized_feed"
    assert jobs[0].posted_at is not None


@pytest.mark.asyncio
async def test_short_role_query_must_match_the_job_title() -> None:
    payload = {
        "jobs": [
            {
                "id": 1,
                "jobTitle": "Chief Marketing Officer",
                "companyName": "Unrelated Co",
                "jobDescription": "Works with a QA team and reviews qualifications.",
                "jobGeo": "LATAM",
                "url": "https://jobs.example/unrelated",
                "pubDate": "2026-08-20T12:00:00Z",
            },
            {
                "id": 2,
                "jobTitle": "QA Automation Engineer",
                "companyName": "Relevant Co",
                "jobDescription": "Automated software testing.",
                "jobGeo": "LATAM",
                "url": "https://jobs.example/qa",
                "pubDate": "2026-08-20T12:00:00Z",
            },
        ]
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload, request=request)
    )
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        jobs = await JobicyConnector(client).search(
            SearchRequest(query="QA", aliases=["QA Engineer", "Software Tester"])
        )

    assert [job.title for job in jobs] == ["QA Automation Engineer"]


def test_restricted_portals_have_no_automated_connector() -> None:
    forbidden = {
        SourceKind.LINKEDIN,
        SourceKind.INDEED,
        SourceKind.GLASSDOOR,
        SourceKind.COMPUTRABAJO,
    }
    assert forbidden.isdisjoint(CONNECTOR_TYPES)
