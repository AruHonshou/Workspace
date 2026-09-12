import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from job_orchestrator.connectors.providers import ProviderSearchPage
from job_orchestrator.schemas import SearchStatus, utc_now
from job_orchestrator.services.job_identity import merge_jobs
from job_orchestrator.services.job_search import (
    JobSearchInput,
    JobSearchService,
    SearchConflict,
)
from job_orchestrator.storage import SQLiteStore
from job_orchestrator.theirstack import TheirStackError, normalize_theirstack_job


def job(number=1, age=1, portal="LinkedIn", title=None):
    return normalize_theirstack_job(
        {
            "id": number,
            "job_title": title or f"QA Engineer {number}",
            "company": "Synthetic Company",
            "description": "Manual testing",
            "url": f"https://www.linkedin.com/jobs/view/{number}",
            "date_posted": (utc_now() - timedelta(hours=age)).isoformat(),
            "scraping_source": portal,
        },
        search_country_code="CR",
    )


class Provider:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def search(self, query):
        self.calls.append(query)
        await asyncio.sleep(0)
        if self.fail:
            raise TheirStackError("TheirStack sin cuota")
        return ProviderSearchPage(
            provider="theirstack",
            jobs=[job(query.page + 1)],
            page=query.page,
            page_size=query.page_size,
            total_available=40,
            can_load_more=query.page == 0,
        )


@pytest.fixture
def service(tmp_path):
    store = SQLiteStore(tmp_path / "search.db")
    store.migrate()
    return JobSearchService(store, Provider())


def query(**kwargs):
    return JobSearchInput(role="QA", country_code="CR", request_id=uuid4(), **kwargs)


@pytest.mark.asyncio
async def test_profile_free_search_caches_and_paginates(service):
    result = await service.search(query(window_days=30))
    assert result.status == "completed"
    assert len(result.jobs) == 1
    assert "profile_id" not in service.store.get_search(result.search_id).model_dump()
    assert service.provider.calls[0].page_size == 20
    assert service.provider.calls[0].max_age_days == 30
    assert service.provider.calls[0].portals == (
        "linkedin",
        "indeed",
        "computrabajo",
        "glassdoor",
    )
    assert (await service.search(query(window_days=30))).cached
    more, duplicate = await asyncio.gather(
        service.more(result.search_id, 1), service.more(result.search_id, 1)
    )
    assert len(more.jobs) == 2
    assert duplicate.cached
    assert len(service.provider.calls) == 2


@pytest.mark.asyncio
async def test_cross_portal_duplicates_merge_and_keep_provenance(service):
    first = job(11, portal="LinkedIn", title="QA Automation Engineer")
    second = job(12, portal="Indeed", title="QA Automation Engineer")
    service.provider.search = lambda query: asyncio.sleep(
        0,
        result=ProviderSearchPage(
            provider="theirstack",
            jobs=[first, second],
            page=0,
            page_size=20,
            total_available=2,
            can_load_more=False,
        ),
    )
    result = await service.search(query())
    assert len(result.jobs) == 1
    assert result.jobs[0].source_portals == ["LinkedIn", "Indeed"]
    assert len(result.jobs[0].source_urls) == 2
    assert service.store.get_job(result.jobs[0].job_id) is not None


@pytest.mark.asyncio
async def test_persisted_cache_survives_service_restart(service):
    result = await service.search(query())
    restarted = JobSearchService(service.store, Provider())
    assert (await restarted.search(query())).search_id == result.search_id
    assert not restarted.provider.calls


@pytest.mark.asyncio
async def test_uncertain_page_never_retries_automatically(service):
    result = await service.search(query())
    service.provider.fail = True
    failed = await service.more(result.search_id, 1)
    assert failed.status == "failed"
    assert len(failed.jobs) == 1
    with pytest.raises(SearchConflict):
        await service.more(result.search_id, 1)
    assert len(service.provider.calls) == 2
    assert (await service.search(query())).cached


@pytest.mark.asyncio
async def test_refresh_idempotency_and_scope_mismatch(service):
    payload = query(refresh=True)
    first, duplicate = await asyncio.gather(
        service.search(payload), service.search(payload)
    )
    assert first.search_id == duplicate.search_id
    assert len(service.provider.calls) == 1
    with pytest.raises(SearchConflict):
        await service.search(payload.model_copy(update={"role": "Developer"}))


def test_common_title_and_company_variants_merge_conservatively() -> None:
    linkedin = job(21, portal="LinkedIn", title="QA Automation Engineer").model_copy(
        update={"company": "Acme Technologies Inc."}
    )
    indeed = job(
        22,
        portal="Indeed",
        title="Quality Assurance Automation Engineer",
    ).model_copy(update={"company": "Acme Technologies"})

    merged = merge_jobs([linkedin, indeed])

    assert len(merged) == 1
    assert {item.source_portal for item in merged[0].job.source_evidence} == {
        "LinkedIn",
        "Indeed",
    }


def test_cross_portal_duplicates_with_location_variants_merge_by_description() -> None:
    description = (
        "Design and execute automated browser tests with Playwright, validate REST APIs, "
        "document reproducible defects, collaborate with developers, and maintain reliable "
        "regression coverage for critical customer journeys across web applications."
    )
    linkedin = job(31, portal="LinkedIn", title="QA Automation Engineer").model_copy(
        update={"location": "San José, Costa Rica", "description": description}
    )
    indeed = job(32, portal="Indeed", title="QA Automation Engineer").model_copy(
        update={
            "location": "San José Province",
            "description": f"{description} Apply through the original company portal.",
        }
    )

    assert len(merge_jobs([linkedin, indeed])) == 1


def test_distinct_vacancies_are_not_merged_by_title_and_company_alone() -> None:
    automation = job(41, portal="LinkedIn", title="QA Engineer").model_copy(
        update={
            "location": "San José",
            "description": (
                "Build browser automation with Playwright and TypeScript, own CI regression "
                "pipelines, triage failures, and improve release feedback for the web platform."
            ),
        }
    )
    manual = job(42, portal="Indeed", title="QA Engineer").model_copy(
        update={
            "location": "Heredia",
            "description": (
                "Execute exploratory mobile testing, review product requirements, document "
                "usability findings, coordinate acceptance sessions, and report customer risks."
            ),
        }
    )

    assert len(merge_jobs([automation, manual])) == 2


@pytest.mark.parametrize("days", [1, 7, 30])
def test_exact_time_boundaries(service, days):
    start = utc_now()
    vacancy = job()
    payload = query(window_days=days)
    vacancy.posted_at = start - timedelta(days=days)
    assert service._accept(vacancy, payload, start)
    vacancy.posted_at -= timedelta(microseconds=1)
    assert service._accept(vacancy, payload, start) is None
    vacancy.posted_at = start + timedelta(seconds=1)
    assert service._accept(vacancy, payload, start) is None


def test_unknown_sources_naive_timestamps_and_day_precision(service):
    payload = query()
    start = utc_now()
    vacancy = job(portal="Unknown")
    assert service._accept(vacancy, payload, start) is None
    vacancy = job()
    vacancy.posted_at = vacancy.posted_at.replace(tzinfo=None)
    assert service._accept(vacancy, payload, start) is None
    vacancy.raw["date_posted"] = (start - timedelta(days=2)).date().isoformat()
    vacancy.posted_at = start.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=2)
    assert service._accept(vacancy, payload, start).date_precision == "day"


@pytest.mark.asyncio
async def test_pending_receipt_after_restart_is_not_reissued(service):
    result = await service.search(query())
    run = service.store.get_search(result.search_id)
    run.status = SearchStatus.RUNNING
    run.result["pending_page"] = 1
    service.store.save_search(run)
    restarted = JobSearchService(service.store, Provider())
    with pytest.raises(SearchConflict):
        await restarted.more(result.search_id, 1)
    assert not restarted.provider.calls


def test_api_search_without_profiles_or_ai(client):
    service = JobSearchService(client.app.state.store, Provider())
    client.app.state.simple_search_service = service
    payload = query().model_dump(mode="json")
    response = client.post("/api/searches", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "raw" not in response.json()["jobs"][0]
    assert "profile_id" not in response.json()
    assert (
        client.get(f"/api/searches/{response.json()['search_id']}").status_code == 200
    )

    saved_payload = {
        "job_id": response.json()["jobs"][0]["job_id"],
        "search_id": response.json()["search_id"],
    }
    saved = client.post("/api/saved-jobs", json=saved_payload)
    assert saved.status_code == 201
    assert saved.json()["job_id"] == saved_payload["job_id"]
    duplicate = client.post("/api/saved-jobs", json=saved_payload)
    assert duplicate.status_code == 201
    assert duplicate.json()["saved_id"] == saved.json()["saved_id"]
    assert len(client.get("/api/saved-jobs").json()) == 1
    assert (
        client.delete(f"/api/saved-jobs/{saved.json()['saved_id']}").status_code == 204
    )
