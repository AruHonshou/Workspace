from __future__ import annotations

import asyncio
import time
from datetime import timedelta
from uuid import uuid4

from job_orchestrator.ai_contracts import (
    AIInvocationResult,
    AIOperation,
    ATSResumeLineProposal,
    ATSResumeProposal,
    ATSResumeSkillProposal,
)
from job_orchestrator.connectors.providers import ProviderSearchPage
from job_orchestrator.schemas import utc_now
from job_orchestrator.services.job_search import JobSearchService
from job_orchestrator.theirstack import normalize_theirstack_job


class JourneyJobProvider:
    """A deterministic provider that never calls a paid or external service."""

    async def search(self, query):
        await asyncio.sleep(0)
        job = normalize_theirstack_job(
            {
                "id": "journey-qa-1",
                "job_title": "QA Automation Engineer",
                "company": "Workspace Test Company",
                "description": (
                    "Required Playwright experience, REST API testing and "
                    "regression test design."
                ),
                "url": "https://www.linkedin.com/jobs/view/journey-qa-1",
                "date_posted": (utc_now() - timedelta(hours=2)).isoformat(),
                "scraping_source": "LinkedIn",
            },
            search_country_code=query.country_code,
        )
        return ProviderSearchPage(
            provider="theirstack",
            jobs=[job],
            page=query.page,
            page_size=query.page_size,
            total_available=1,
            can_load_more=False,
        )


class JourneyDocumentRegistry:
    """Only the ATS proposal is model-shaped; its evidence stays verifiable."""

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, operation: AIOperation, payload: dict):
        if operation != AIOperation.ATS_RESUME:
            raise AssertionError(operation)
        self.calls += 1
        fact = payload["confirmed_records"][0]
        proposed_text = fact["text"]
        if self.calls > 1 or payload.get("required_revision"):
            proposed_text = (
                "Built and maintained Playwright regression coverage while validating "
                "REST APIs with Postman."
            )
        proposal = ATSResumeProposal(
            language="en",
            headline="QA Automation Engineer",
            professional_summary=(
                "QA professional with confirmed browser automation experience."
            ),
            summary_record_ids=[fact["fact_id"]],
            skills=[
                ATSResumeSkillProposal(
                    text="Playwright", record_ids=[fact["fact_id"]]
                )
            ],
            experience=[
                ATSResumeLineProposal(
                    original_text=fact["text"],
                    proposed_text=proposed_text,
                    record_ids=[fact["fact_id"]],
                )
            ],
        )
        return AIInvocationResult(
            content=proposal.model_dump_json(),
            model="journey-fixture",
            structured=proposal,
        )


def test_complete_modern_product_journey(client) -> None:
    """Search -> save -> analyze -> guide -> evidence-checked ATS documents."""

    imported = client.post(
        "/api/profiles/import",
        params={"language": "en"},
        files={
            "file": (
                "qa-resume.txt",
                (
                    b"Built Playwright regression tests and validated REST APIs "
                    b"with Postman."
                ),
                "text/plain",
            )
        },
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]
    client.post(f"/api/profiles/{profile_id}/confirm").raise_for_status()
    client.post(
        f"/api/profiles/{profile_id}/cloud-consent",
        json={
            "granted": True,
            "purposes": ["fit_analysis", "document_generation"],
        },
    ).raise_for_status()

    client.app.state.simple_search_service = JobSearchService(
        client.app.state.store,
        JourneyJobProvider(),
    )
    searched = client.post(
        "/api/searches",
        json={
            "role": "QA",
            "country_code": "CR",
            "window_days": 7,
            "portals": ["linkedin"],
            "request_id": str(uuid4()),
        },
    )
    searched.raise_for_status()
    search = searched.json()
    assert search["status"] == "completed"
    assert len(search["jobs"]) == 1

    saved_response = client.post(
        "/api/saved-jobs",
        json={
            "job_id": search["jobs"][0]["job_id"],
            "search_id": search["search_id"],
        },
    )
    saved_response.raise_for_status()
    saved_id = saved_response.json()["saved_id"]

    analysis = client.post(
        f"/api/saved-jobs/{saved_id}/analyses",
        params={"profile_id": profile_id},
    )
    assert analysis.status_code == 201, analysis.text
    assert analysis.json()["requirement_analysis"]

    started_guide = client.post(
        f"/api/saved-jobs/{saved_id}/interview-guides",
        params={"profile_id": profile_id},
        headers={"Idempotency-Key": "complete-modern-journey-guide"},
    )
    assert started_guide.status_code == 202, started_guide.text
    guide = started_guide.json()
    deadline = time.monotonic() + 8
    while guide["status"] in {"preparing", "reviewing", "rendering"}:
        assert time.monotonic() < deadline, guide
        time.sleep(0.03)
        current = client.get(
            f"/api/saved-jobs/{saved_id}/interview-guides/{profile_id}"
        )
        current.raise_for_status()
        guide = current.json()
    assert guide["status"] == "ready", guide
    guide_pdf = client.get(
        f"/api/saved-jobs/{saved_id}/interview-guides/{profile_id}/document.pdf"
    )
    assert guide_pdf.status_code == 200
    assert guide_pdf.content.startswith(b"%PDF")

    client.app.state.ai_client = JourneyDocumentRegistry()
    proposed_resume = client.post(
        f"/api/saved-jobs/{saved_id}/ats-resumes",
        params={"profile_id": profile_id},
        headers={"Idempotency-Key": "complete-modern-journey-resume"},
    )
    assert proposed_resume.status_code == 202, proposed_resume.text
    version_id = proposed_resume.json()["version_id"]
    approved = client.patch(
        f"/api/ats-resumes/{version_id}/approve",
        json={"approved": True},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ready"
    assert client.get(f"/api/ats-resumes/{version_id}.pdf").content.startswith(b"%PDF")
    assert client.get(f"/api/ats-resumes/{version_id}.docx").content.startswith(b"PK")

    exported = client.get("/api/data/export")
    exported.raise_for_status()
    snapshot = exported.json()
    assert any(item["search_id"] == search["search_id"] for item in snapshot["searches"])
    assert any(item["saved_id"] == saved_id for item in snapshot["saved_jobs"])
    assert snapshot["fit_analyses"]
    assert snapshot["interview_guides"]
    assert any(item["version_id"] == version_id for item in snapshot["ats_resumes"])
