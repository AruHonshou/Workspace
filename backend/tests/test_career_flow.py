from __future__ import annotations

import time
from datetime import timedelta

from conftest import wait_for_run
from job_orchestrator.career import (
    build_deep_analysis,
    cloud_safe_verified_facts,
    expand_role,
    filter_verified_recent_jobs,
)
from job_orchestrator.ranking import normalize_job
from job_orchestrator.schemas import SourceKind, utc_now
from pypdf import PdfReader


def _profile(client):
    response = client.post(
        "/api/profiles",
        json={
            "name": "Ada Local",
            "summary": "QA engineer",
            "facts": [
                {
                    "category": "skill",
                    "text": "Designed automated API tests with Python and SQL.",
                    "verified": True,
                },
                {
                    "category": "experience",
                    "text": "Documented defects and collaborated with software teams.",
                    "verified": True,
                },
            ],
            "confirmed": True,
        },
    )
    response.raise_for_status()
    return response.json()


def _wait_for_guide(client, interest_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        interest = client.get(f"/api/interests/{interest_id}").json()
        if interest["guide_status"] in {"ready", "failed"}:
            return interest
        time.sleep(0.02)
    raise AssertionError("Interview guide did not finish")


def test_role_expansion_is_bilingual_and_visible() -> None:
    assert "QA Engineer" in expand_role("QA")
    assert "Software Engineer" in expand_role("Desarrollador")


def test_bilingual_resumes_are_required_and_selected_by_job_language(client) -> None:
    spanish = client.post(
        "/api/profiles/import",
        params={"language": "es"},
        files={
            "file": (
                "cv-es.txt",
                b"Experiencia automatizando pruebas de API con Selenium y documentando defectos.",
                "text/plain",
            )
        },
    )
    assert spanish.status_code == 201, spanish.text
    profile_id = spanish.json()["profile"]["profile_id"]
    assert client.post(f"/api/profiles/{profile_id}/confirm").status_code == 409

    english = client.post(
        "/api/profiles/import",
        params={"language": "en", "profile_id": profile_id},
        files={
            "file": (
                "cv-en.txt",
                b"Built automated API tests with Playwright and documented defects for software releases.",
                "text/plain",
            )
        },
    )
    assert english.status_code == 201, english.text
    payload = english.json()["profile"]
    assert set(payload["resumes"]) == {"es", "en"}
    assert {fact["language"] for fact in payload["facts"]} == {"es", "en"}
    assert client.post(f"/api/profiles/{profile_id}/confirm").status_code == 200

    profile = client.app.state.store.get_profile(profile_id)
    english_job = normalize_job(
        source=SourceKind.MANUAL,
        external_id="english-analysis",
        title="QA Automation Engineer",
        company="Example",
        description="Must have Playwright experience for automated API testing.",
        location="Costa Rica",
        url="https://jobs.example.test/en",
        posted_at=utc_now(),
    )
    spanish_job = normalize_job(
        source=SourceKind.MANUAL,
        external_id="spanish-analysis",
        title="Ingeniero de calidad",
        company="Ejemplo",
        description="Requisitos y experiencia: se requiere experiencia con Selenium.",
        location="Costa Rica",
        url="https://jobs.example.test/es",
        posted_at=utc_now(),
    )
    english_analysis = build_deep_analysis(english_job, profile)
    spanish_analysis = build_deep_analysis(spanish_job, profile)
    assert english_analysis.resume_language == "en"
    assert "Playwright" in english_analysis.matched_requirements[0]["evidence"]
    assert spanish_analysis.resume_language == "es"
    assert "Selenium" in spanish_analysis.matched_requirements[0]["evidence"]


def test_strict_thirty_day_window_excludes_unknown_old_and_non_https() -> None:
    now = utc_now()
    recent = normalize_job(
        source=SourceKind.HIMALAYAS,
        external_id="recent",
        title="QA Engineer",
        company="Acme",
        description="Requires API testing experience.",
        location="Remote",
        remote=True,
        url="https://jobs.example.test/recent",
        posted_at=now - timedelta(hours=2),
    )
    old = recent.model_copy(
        update={"external_id": "old", "posted_at": now - timedelta(days=31)}
    )
    unknown = recent.model_copy(update={"external_id": "unknown", "posted_at": None})
    insecure = recent.model_copy(
        update={"external_id": "insecure", "url": "http://jobs.example.test/insecure"}
    )

    accepted, rejected = filter_verified_recent_jobs(
        [recent, old, unknown, insecure], search_started_at=now
    )

    assert [job.external_id for job in accepted] == ["recent"]
    assert rejected == {
        "missing_date": 1,
        "outside_30d": 1,
        "invalid_url": 1,
        "outside_scope": 0,
    }


def test_thirty_day_window_includes_exact_boundary() -> None:
    now = utc_now()
    boundary = normalize_job(
        source=SourceKind.JOBICY,
        external_id="boundary",
        title="QA Engineer",
        company="Boundary Labs",
        description="QA testing",
        location="Remote - LATAM",
        remote=True,
        url="https://jobs.example.test/boundary",
        posted_at=now - timedelta(days=30),
    )
    accepted, rejected = filter_verified_recent_jobs([boundary], search_started_at=now)
    assert [job.external_id for job in accepted] == ["boundary"]
    assert not any(rejected.values())


def test_cloud_payload_removes_contact_facts(client) -> None:
    profile = client.post(
        "/api/profiles",
        json={
            "name": "Ada Local",
            "email": "ada@example.test",
            "facts": [
                {"category": "contact", "text": "ada@example.test", "verified": True},
                {"category": "contact", "text": "+506 8888-7777", "verified": True},
                {"category": "skill", "text": "Automated API tests with Python.", "verified": True},
            ],
            "confirmed": True,
        },
    ).json()
    stored = client.app.state.store.get_profile(profile["profile_id"])
    safe = cloud_safe_verified_facts(stored)
    assert safe == [{
        "fact_id": profile["facts"][2]["fact_id"],
        "text": "Automated API tests with Python.",
        "category": "skill",
    }]


def test_manual_portal_import_requires_exact_date_and_never_becomes_connector(client) -> None:
    missing_date = client.post(
        "/api/jobs/manual",
        json={
            "source": "linkedin",
            "title": "QA Engineer",
            "company": "Example",
            "description": "A sufficiently complete copied QA job description.",
            "url": "https://www.linkedin.com/jobs/view/123",
        },
    )
    assert missing_date.status_code == 422
    forbidden_source = client.post(
        "/api/jobs/manual",
        json={
            "source": "jobicy",
            "title": "QA Engineer",
            "company": "Example",
            "description": "A sufficiently complete copied QA job description.",
            "url": "https://jobicy.com/jobs/123",
            "posted_at": utc_now().isoformat(),
        },
    )
    assert forbidden_source.status_code == 422


def test_search_analysis_interest_and_pdf_are_end_to_end(client) -> None:
    profile = _profile(client)
    now = utc_now()

    async def connector_search(request):
        assert "QA Engineer" in request.aliases
        return (
            [
                normalize_job(
                    source=SourceKind.HIMALAYAS,
                    external_id="qa-1",
                    title="QA Automation Engineer",
                    company="Example Labs",
                    description=(
                        "Required experience with Python API testing. "
                        "Must document defects and collaborate with software teams."
                    ),
                    location="Remote - Latin America",
                    remote=True,
                    url="https://careers.example.test/qa-1",
                    posted_at=now - timedelta(hours=3),
                )
            ],
            {},
        )

    client.app.state.connector_search = connector_search
    created = client.post(
        "/api/career/searches",
        json={"profile_id": profile["profile_id"], "role": "QA"},
    )
    assert created.status_code == 202, created.text
    run = wait_for_run(client, created.json()["run_id"])
    assert run["status"] == "completed"
    assert run["result"]["aliases"][1] == "QA Engineer"
    assert len(run["result"]["career_results"]) == 1
    result = run["result"]["career_results"][0]
    assert result["freshness_verified"] is True
    assert result["official_url_verified"] is True

    analysis = client.get(
        f"/api/jobs/{result['job_id']}/analysis",
        params={"profile_id": profile["profile_id"]},
    )
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["matched_requirements"]
    assert "perfect" not in analysis.text.casefold()

    payload = {
        "profile_id": profile["profile_id"],
        "run_id": run["run_id"],
    }
    first = client.post(f"/api/jobs/{result['job_id']}/interests", json=payload)
    second = client.post(f"/api/jobs/{result['job_id']}/interests", json=payload)
    assert first.status_code == second.status_code == 202
    assert first.json()["interest_id"] == second.json()["interest_id"]
    assert first.json()["guide_run_id"]
    ready = _wait_for_guide(client, first.json()["interest_id"])
    assert ready["guide_status"] == "ready"
    assert ready["guide_artifact_id"]
    guide_events = client.app.state.store.list_events(ready["guide_run_id"])
    assert {event.ui.template_key for event in guide_events} >= {
        "event.career.guide.analyzing",
        "event.career.guide.writing",
        "event.career.guide.rendering",
        "event.career.guide.ready",
    }
    assert {event.actor_id for event in guide_events} == {"career_assistant"}
    assert guide_events[-1].type == "run_completed"

    guide = client.get(f"/api/interests/{first.json()['interest_id']}/guide.pdf")
    assert guide.status_code == 200
    assert guide.headers["content-type"].startswith("application/pdf")
    reader = PdfReader(__import__("io").BytesIO(guide.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Interview guide" in text
    assert "Python" in text


def test_one_failed_configured_source_keeps_other_results(client) -> None:
    profile = _profile(client)
    now = utc_now()
    client.app.state.settings.career_ats_boards = ["ashby:unavailable-board"]

    async def connector_search(request):
        if request.sources == [SourceKind.ASHBY]:
            raise RuntimeError("private connector detail")
        return ([normalize_job(
            source=SourceKind.HIMALAYAS,
            external_id="qa-survivor",
            title="QA Engineer",
            company="Survivor Labs",
            description="Python testing",
            location="Remote - Latin America",
            remote=True,
            url="https://careers.example.test/qa-survivor",
            posted_at=now - timedelta(hours=2),
        )], {})

    client.app.state.connector_search = connector_search
    created = client.post(
        "/api/career/searches",
        json={"profile_id": profile["profile_id"], "role": "QA"},
    )
    run = wait_for_run(client, created.json()["run_id"])

    assert run["status"] == "completed"
    assert len(run["result"]["career_results"]) == 1
    assert run["result"]["coverage"]["sources_failed"]
    assert "private connector detail" not in str(run["result"])


def test_model_enrichment_failure_does_not_hide_search_results(client) -> None:
    profile = _profile(client)
    now = utc_now()

    class FailingRegistry:
        def invoke(self, *_args, **_kwargs):
            raise RuntimeError("provider response was unavailable")

    async def connector_search(_request):
        return ([normalize_job(
            source=SourceKind.JOBICY,
            external_id="qa-without-enrichment",
            title="QA Engineer",
            company="Resilient Labs",
            description="API testing and defect documentation",
            location="Remote - Latin America",
            remote=True,
            url="https://careers.example.test/qa-without-enrichment",
            posted_at=now - timedelta(hours=2),
        )], {})

    client.app.state.agent_registry = FailingRegistry()
    client.app.state.connector_search = connector_search
    created = client.post(
        "/api/career/searches",
        json={"profile_id": profile["profile_id"], "role": "QA"},
    )
    run = wait_for_run(client, created.json()["run_id"])

    assert run["status"] == "completed"
    assert len(run["result"]["career_results"]) == 1
    assert run["result"]["coverage"]["model_warnings"] == [
        "role_expansion_unavailable",
    ]
