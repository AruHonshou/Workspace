from __future__ import annotations

import httpx
import pytest

from job_orchestrator.config import Settings
from job_orchestrator.theirstack import (
    TheirStackClient,
    TheirStackError,
    normalize_theirstack_job,
)


def _job(**overrides: object) -> dict[str, object]:
    return {
        "id": 42,
        "job_title": "QA Engineer",
        "company": "Prueba CR",
        "description": "Automatización, pruebas de API y aseguramiento de calidad.",
        "location": "San José, Costa Rica",
        "date_posted": "2026-08-20T12:00:00Z",
        "source_url": "https://www.linkedin.com/jobs/view/42",
        "url": "https://www.linkedin.com/jobs/view/42",
        "final_url": "https://careers.example.test/jobs/42",
        "workplace_types": ["hybrid"],
        **overrides,
    }


def test_normalization_prioritizes_company_url_and_preserves_origin() -> None:
    job = normalize_theirstack_job(_job())
    assert job is not None
    assert str(job.url) == "https://careers.example.test/jobs/42"
    assert str(job.source_url) == "https://www.linkedin.com/jobs/view/42"
    assert job.source_portal == "LinkedIn"
    assert job.provider == "theirstack"
    assert job.apply_url_type == "company"


def test_normalization_labels_portal_fallback_without_calling_it_official() -> None:
    job = normalize_theirstack_job(_job(final_url=None))
    assert job is not None
    assert str(job.url) == "https://www.linkedin.com/jobs/view/42"
    assert job.apply_url_type == "portal"
    assert job.verification_level == "authorized_feed"


def test_closed_or_incomplete_jobs_are_excluded() -> None:
    assert normalize_theirstack_job(_job(closed_at="2026-08-21T00:00:00Z")) is None
    assert normalize_theirstack_job(_job(description="")) is None
    assert normalize_theirstack_job(_job(date_posted=None)) is None


class _Credential:
    def __init__(self, value: str | None):
        self.value = value

    def get(self) -> str | None:
        return self.value


class _FakeAsyncClient:
    last_json: dict[str, object] | None = None
    last_get_path: str | None = None

    def __init__(self, **_: object):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, path: str, *, headers: dict[str, str]):
        assert headers["Authorization"] == "Bearer ts-secret"
        self.__class__.last_get_path = path
        request = httpx.Request("GET", f"https://api.theirstack.com{path}")
        return httpx.Response(200, request=request, json={"api_credits": 975})

    async def post(self, path: str, *, json: dict[str, object], headers: dict[str, str]):
        assert path == "/v1/jobs/search"
        assert headers["Authorization"] == "Bearer ts-secret"
        self.__class__.last_json = json
        request = httpx.Request("POST", f"https://api.theirstack.com{path}")
        return httpx.Response(
            200,
            request=request,
            json={"data": [_job(id=index, job_title=f"QA Engineer {index}") for index in range(25)], "total_results": 60},
        )


@pytest.mark.asyncio
async def test_search_uses_cost_bounded_costa_rica_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("job_orchestrator.theirstack.httpx.AsyncClient", _FakeAsyncClient)
    client = TheirStackClient(Settings(), _Credential("ts-secret"))  # type: ignore[arg-type]
    page = await client.search_page(role="QA", aliases=["QA Engineer"], page=0)
    assert len(page.jobs) == 25
    assert page.total_available == 60
    assert page.can_load_more is True
    assert _FakeAsyncClient.last_json == {
        "job_title_or": ["QA", "QA Engineer"],
        "job_country_code_or": ["CR"],
        "posted_at_max_age_days": 30,
        "is_closed": False,
        "page": 0,
        "limit": 25,
        "include_total_results": True,
    }


@pytest.mark.asyncio
async def test_validation_uses_credit_balance_without_retrieving_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("job_orchestrator.theirstack.httpx.AsyncClient", _FakeAsyncClient)
    client = TheirStackClient(Settings(), _Credential(None))  # type: ignore[arg-type]
    credits = await client.validate_key("ts-secret")
    assert credits == 975
    assert _FakeAsyncClient.last_get_path == "/v0/billing/credit-balance"


@pytest.mark.asyncio
async def test_search_without_key_fails_before_network() -> None:
    client = TheirStackClient(Settings(), _Credential(None))  # type: ignore[arg-type]
    with pytest.raises(TheirStackError, match="no está configurado"):
        await client.search_page(role="QA", aliases=[], page=0)
