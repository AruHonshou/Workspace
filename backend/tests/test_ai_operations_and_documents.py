from __future__ import annotations

import time
from io import BytesIO

from fastapi.testclient import TestClient
from job_orchestrator.ai_contracts import (
    AIInvocationResult,
    AIOperation,
    ATSResumeLineProposal,
    ATSResumeProposal,
    ATSResumeSkillProposal,
    FitAnalystProposal,
    FitMappingProposal,
    FitRequirementNarrative,
    LinkedInOptimizationProposal,
    LinkedInSectionProposal,
)
from job_orchestrator.api import create_app
from job_orchestrator.ats_documents import build_ats_document
from job_orchestrator.config import Settings
from job_orchestrator.ranking import normalize_job
from job_orchestrator.schemas import (
    ConfirmationStatus,
    LinkedInProfileSnapshot,
    LinkedInSectionInput,
    Profile,
    ProfileFact,
    ResumeVariant,
    SearchRecord,
    SearchStatus,
    SourceKind,
    utc_now,
)
from job_orchestrator.services.ai_operations import (
    build_ats_resume_operation,
    build_linkedin_optimization_operation,
    run_fit_analysis,
)
from reportlab.pdfgen.canvas import Canvas


def _complete_linkedin_sections(fact_id: str) -> list[LinkedInSectionProposal]:
    copy = {
        "headline": "QA Engineer | Playwright",
        "about": "QA professional focused on reliable browser automation.",
        "experience": "Built regression test coverage with Playwright for Acme in 2025.",
        "education": "Confirmed education and continuous professional learning.",
        "skills": "Playwright · regression testing",
        "certifications": "Confirmed certifications appear here when available.",
    }
    return [
        LinkedInSectionProposal(
            section=section,
            proposed_text=text,
            rationale="Uses confirmed profile evidence and the selected role.",
            keywords=["QA", "Playwright"],
            record_ids=[fact_id],
        )
        for section, text in copy.items()
    ]


class DocumentRegistry:
    def __init__(self) -> None:
        self.ats_calls: list[dict] = []

    def invoke(self, operation: AIOperation, payload: dict):
        facts = payload.get("confirmed_records", [])
        if operation == AIOperation.ATS_RESUME:
            self.ats_calls.append(payload)
            fact = facts[0]
            proposal = ATSResumeProposal(
                language="en",
                headline="QA Engineer",
                professional_summary="QA professional with confirmed automation experience.",
                summary_record_ids=[fact["fact_id"]],
                skills=[
                    ATSResumeSkillProposal(
                        text="Playwright", record_ids=[fact["fact_id"]]
                    )
                ],
                experience=[
                    ATSResumeLineProposal(
                        original_text=fact["text"],
                        proposed_text=(
                            "Built regression test coverage with Playwright for Acme in "
                            "2025."
                            if payload.get("required_revision")
                            else fact["text"]
                        ),
                        record_ids=[fact["fact_id"]],
                    )
                ],
            )
        elif operation == AIOperation.LINKEDIN_OPTIMIZATION:
            proposal = LinkedInOptimizationProposal(
                sections=_complete_linkedin_sections(facts[0]["fact_id"])
            )
        else:  # pragma: no cover - this registry is intentionally bounded
            raise AssertionError(operation)
        return AIInvocationResult(
            content=proposal.model_dump_json(), model="fixture", structured=proposal
        )


def _profile() -> Profile:
    return Profile(
        name="Ada",
        confirmed=True,
        resumes={
            "en": ResumeVariant(
                document_id="document_en",
                language="en",
                filename="resume.txt",
                text="Built Playwright regression tests for Acme in 2025. ada@example.com",
                extraction_method="text",
                confirmation_status=ConfirmationStatus.CONFIRMED,
            )
        },
        facts=[
            ProfileFact(
                category="experience",
                text="Built Playwright regression tests for Acme in 2025.",
                language="en",
                verified=True,
            )
        ],
    )


def _job():
    return normalize_job(
        source=SourceKind.MANUAL,
        external_id="global-qa",
        title="QA Engineer",
        company="Example",
        description="Required Playwright experience and regression testing.",
        location="Remote",
        remote=True,
        url="https://jobs.example.test/global-qa",
        posted_at=utc_now(),
    )


def test_structured_services_are_executable() -> None:
    profile = _profile()
    job = _job()
    analysis = run_fit_analysis(job, profile, None)
    assert analysis.job_id == job.job_id
    assert analysis.requirement_analysis

    registry = DocumentRegistry()
    ats = build_ats_resume_operation(registry).invoke(
        {"job": job.model_dump(mode="json"), "profile": profile.model_dump(mode="json")}
    )
    assert ats["stage"] == "awaiting_approval"
    assert ats["document"]["experience"]
    assert (
        ats["document"]["experience"][0]["proposed_text"]
        != ats["document"]["experience"][0]["original_text"]
    )
    assert len(registry.ats_calls) == 2
    assert registry.ats_calls[0]["targeting_context"]["supported_requirements"]
    assert registry.ats_calls[1]["required_revision"]["problems"]

    linkedin = build_linkedin_optimization_operation(registry).invoke(
        {
            "snapshot": LinkedInProfileSnapshot(
                profile_id=profile.profile_id,
                profile_revision=profile.revision,
                language="en",
                target_roles=["QA Engineer"],
                sections=LinkedInSectionInput(headline="QA professional"),
            ).model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
        }
    )
    assert linkedin["stage"] == "completed"
    assert linkedin["sections"][0]["section"] == "headline"
    assert linkedin["sections"][0]["evidence"] == [
        "Built Playwright regression tests for Acme in 2025."
    ]
    assert "fact_" not in str(linkedin["sections"][0]["evidence"])


def test_fit_analysis_ignores_unrelated_but_verified_model_evidence() -> None:
    profile = _profile()
    overlooked = ProfileFact(
        category="experience",
        text="Validated release readiness with SQL-backed quality reports.",
        language="en",
        verified=True,
    )
    profile.facts.append(overlooked)
    job = _job()

    class FitRegistry:
        def invoke(self, operation: AIOperation, payload: dict):
            assert operation == AIOperation.FIT_ANALYSIS
            proposal = FitAnalystProposal(
                mappings=[
                    FitMappingProposal(
                        job_id=job.job_id,
                        fact_ids=[overlooked.fact_id],
                    )
                ],
                executive_summary="The profile offers relevant, verified quality evidence.",
                requirement_notes=[
                    FitRequirementNarrative(
                        requirement_index=0,
                        explanation="The SQL quality reports provide transferable evidence.",
                        fact_ids=[overlooked.fact_id],
                    )
                ],
            )
            return AIInvocationResult(
                content=proposal.model_dump_json(),
                model="fixture",
                structured=proposal,
            )

    analysis = run_fit_analysis(
        job,
        profile,
        FitRegistry(),
        require_model=True,
        output_language="es",
    )

    assert overlooked.fact_id not in analysis.requirement_analysis[0].fact_ids
    assert overlooked.text not in analysis.requirement_analysis[0].evidence
    assert analysis.analysis_language == "es"


def test_ats_skills_must_exist_in_their_cited_evidence() -> None:
    profile = _profile()
    job = _job()
    fact = profile.facts[0]
    proposal = ATSResumeProposal(
        language="en",
        headline="QA Engineer",
        professional_summary="QA professional with confirmed testing experience.",
        summary_record_ids=[fact.fact_id],
        skills=[
            ATSResumeSkillProposal(
                text="Selenium",
                record_ids=[fact.fact_id],
            )
        ],
        experience=[
            ATSResumeLineProposal(
                original_text=fact.text,
                proposed_text="Built regression coverage with Playwright for Acme in 2025.",
                record_ids=[fact.fact_id],
            )
        ],
    )

    document, issues = build_ats_document(profile, job, proposal)

    assert document.skills == []
    assert any("skill" in issue.casefold() for issue in issues)


def test_ats_quality_warning_keeps_safe_draft_available_for_review() -> None:
    profile = _profile()
    job = _job()

    class ConservativeRegistry:
        def invoke(self, operation: AIOperation, payload: dict):
            assert operation == AIOperation.ATS_RESUME
            fact = payload["confirmed_records"][0]
            proposal = ATSResumeProposal(
                language="en",
                headline="QA Engineer",
                professional_summary="QA professional with confirmed testing experience.",
                summary_record_ids=[fact["fact_id"]],
                skills=[
                    ATSResumeSkillProposal(
                        text="Playwright", record_ids=[fact["fact_id"]]
                    )
                ],
                experience=[
                    ATSResumeLineProposal(
                        original_text=fact["text"],
                        proposed_text=fact["text"],
                        record_ids=[fact["fact_id"]],
                    )
                ],
            )
            return AIInvocationResult(
                content=proposal.model_dump_json(),
                model="fixture",
                structured=proposal,
            )

    result = build_ats_resume_operation(ConservativeRegistry()).invoke(
        {
            "job": job.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
            "stage": "queued",
        }
    )

    assert result["stage"] == "awaiting_approval"
    assert result["document"]["experience"]
    assert any("copied" in issue.casefold() for issue in result["review_issues"])


def test_linkedin_generation_receives_the_complete_redacted_context() -> None:
    profile = _profile()
    profile.summary = "QA engineer with Playwright experience. ada@example.com"
    profile.facts.append(
        ProfileFact(
            category="skill",
            text="SQL",
            language="en",
            verified=True,
        )
    )
    captured: dict[str, object] = {}

    class CaptureRegistry:
        def invoke(self, operation: AIOperation, payload: dict):
            assert operation == AIOperation.LINKEDIN_OPTIMIZATION
            captured.update(payload)
            proposal = LinkedInOptimizationProposal(
                sections=_complete_linkedin_sections(
                    payload["confirmed_records"][0]["fact_id"]
                )
            )
            return AIInvocationResult(
                content=proposal.model_dump_json(), model="fixture", structured=proposal
            )

    snapshot = LinkedInProfileSnapshot(
        profile_id=profile.profile_id,
        profile_revision=profile.revision,
        language="en",
        target_roles=["QA Engineer"],
        source_text="Headline\nQA Engineer\nSkills\nPlaywright\nSQL\nOther section",
        sections=LinkedInSectionInput(headline="QA Engineer"),
    )
    result = build_linkedin_optimization_operation(CaptureRegistry()).invoke(
        {
            "snapshot": snapshot.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
        }
    )
    records = captured["confirmed_records"]
    assert isinstance(records, list)
    assert {item["text"] for item in records} >= {
        "Built Playwright regression tests for Acme in 2025.",
        "SQL",
    }
    assert captured["linkedin_export_text"].startswith("Headline")
    assert "Built Playwright regression tests" in captured["resume_export_text"]
    assert "ada@example.com" not in str(captured["resume_export_text"])
    context = captured["profile_context"]
    assert isinstance(context, dict)
    assert context["target_roles"] == ["QA Engineer"]
    assert "ada@example.com" not in str(context)
    assert "fact_id" not in result["sections"][0]["proposed_text"]
    assert len(result["sections"]) == 6


def test_resume_translation_workflow_is_not_exposed(client) -> None:
    response = client.post(
        "/api/profiles/profile_missing/resume-translations",
        json={"source_language": "en", "target_language": "es"},
    )
    assert response.status_code == 404


def test_documents_require_an_approved_variant_in_the_job_language(client) -> None:
    imported = client.post(
        "/api/profiles/import",
        params={"language": "en-US"},
        files={
            "file": (
                "resume.txt",
                b"Built Playwright regression tests and documented defects.",
                "text/plain",
            )
        },
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]
    confirmed = client.post(f"/api/profiles/{profile_id}/confirm")
    confirmed.raise_for_status()
    client.post(
        f"/api/profiles/{profile_id}/cloud-consent",
        json={"granted": True, "purposes": ["document_generation"]},
    ).raise_for_status()
    job = normalize_job(
        source=SourceKind.MANUAL,
        external_id="es-role",
        title="Ingeniero QA",
        company="Ejemplo",
        description=(
            "Puesto que exige experiencia, habilidades en pruebas y responsabilidades "
            "de calidad para la empresa."
        ),
        location="Costa Rica",
        remote=True,
        url="https://jobs.example.test/es-role",
        posted_at=utc_now(),
        raw={"language": "es"},
    )
    client.app.state.store.save_job(job)
    run = client.app.state.store.save_search(
        SearchRecord(
            status=SearchStatus.COMPLETED,
            request={"flow": "simple_search"},
            result={"jobs": [{"job_id": job.job_id}]},
        )
    )
    saved_response = client.post(
        "/api/saved-jobs",
        json={"job_id": job.job_id, "search_id": run.search_id},
    )
    saved_response.raise_for_status()
    saved_id = saved_response.json()["saved_id"]

    ats = client.post(
        f"/api/saved-jobs/{saved_id}/ats-resumes", params={"profile_id": profile_id}
    )
    guide = client.post(
        f"/api/saved-jobs/{saved_id}/interview-guides",
        params={"profile_id": profile_id},
    )

    assert ats.status_code == guide.status_code == 409
    assert "CV confirmado en es" in ats.json()["detail"]
    assert "CV confirmado en es" in guide.json()["detail"]


def test_ats_resume_api_requires_approval_then_exports_pdf_and_docx(client) -> None:
    imported = client.post(
        "/api/profiles/import",
        params={"language": "en"},
        files={
            "file": (
                "resume.txt",
                b"Built Playwright regression tests for Acme in 2025.",
                "text/plain",
            )
        },
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]
    client.post(f"/api/profiles/{profile_id}/confirm").raise_for_status()
    client.post(
        f"/api/profiles/{profile_id}/cloud-consent",
        json={"granted": True, "purposes": ["document_generation"]},
    ).raise_for_status()
    client.app.state.ai_client = DocumentRegistry()
    job = client.app.state.store.save_job(_job())
    run = client.app.state.store.save_search(
        SearchRecord(
            status=SearchStatus.COMPLETED,
            request={"flow": "simple_search"},
            result={"jobs": [{"job_id": job.job_id}]},
        )
    )
    saved = client.post(
        "/api/saved-jobs",
        json={"job_id": job.job_id, "search_id": run.search_id},
    )
    saved.raise_for_status()

    proposed = client.post(
        f"/api/saved-jobs/{saved.json()['saved_id']}/ats-resumes",
        params={"profile_id": profile_id},
        headers={"Idempotency-Key": "ats-happy-path"},
    )

    assert proposed.status_code == 202, proposed.text
    version = proposed.json()
    assert version["status"] == "awaiting_approval"
    assert version["pdf_path"] is None
    assert version["docx_path"] is None

    unchanged = client.post(
        f"/api/saved-jobs/{saved.json()['saved_id']}/ats-resumes",
        params={"profile_id": profile_id},
    )
    regenerated = client.post(
        f"/api/saved-jobs/{saved.json()['saved_id']}/ats-resumes",
        params={"profile_id": profile_id, "regenerate": True},
    )
    assert unchanged.json()["version_id"] == version["version_id"]
    assert regenerated.status_code == 202, regenerated.text
    assert regenerated.json()["version"] == version["version"] + 1
    version = regenerated.json()

    approved = client.patch(
        f"/api/ats-resumes/{version['version_id']}/approve",
        json={"approved": True},
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ready"
    pdf = client.get(f"/api/ats-resumes/{version['version_id']}.pdf")
    docx = client.get(f"/api/ats-resumes/{version['version_id']}.docx")
    assert pdf.status_code == docx.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert docx.content.startswith(b"PK")


def test_ats_resume_versions_are_independent_for_each_profile(client) -> None:
    profile_ids: list[str] = []
    for index in range(2):
        imported = client.post(
            "/api/profiles/import",
            params={"language": "en"},
            files={
                "file": (
                    f"resume-{index}.txt",
                    b"Built Playwright regression tests for Acme in 2025.",
                    "text/plain",
                )
            },
        )
        imported.raise_for_status()
        profile_id = imported.json()["profile"]["profile_id"]
        client.post(f"/api/profiles/{profile_id}/confirm").raise_for_status()
        client.post(
            f"/api/profiles/{profile_id}/cloud-consent",
            json={"granted": True, "purposes": ["document_generation"]},
        ).raise_for_status()
        profile_ids.append(profile_id)

    client.app.state.ai_client = DocumentRegistry()
    job = client.app.state.store.save_job(_job())
    run = client.app.state.store.save_search(
        SearchRecord(
            status=SearchStatus.COMPLETED,
            request={"flow": "simple_search"},
            result={"jobs": [{"job_id": job.job_id}]},
        )
    )
    saved = client.post(
        "/api/saved-jobs",
        json={"job_id": job.job_id, "search_id": run.search_id},
    )
    saved.raise_for_status()
    saved_id = saved.json()["saved_id"]

    versions = []
    for index, profile_id in enumerate(profile_ids):
        response = client.post(
            f"/api/saved-jobs/{saved_id}/ats-resumes",
            params={"profile_id": profile_id},
            headers={"Idempotency-Key": f"ats-profile-{index}"},
        )
        assert response.status_code == 202, response.text
        versions.append(response.json())

    assert versions[0]["resume_id"] != versions[1]["resume_id"]
    assert versions[0]["version"] == versions[1]["version"] == 1


def test_saved_job_interview_guide_completes_and_downloads_from_modern_api(
    client,
) -> None:
    imported = client.post(
        "/api/profiles/import",
        params={"language": "en"},
        files={
            "file": (
                "resume.txt",
                b"Built Playwright regression tests and validated REST APIs with Postman.",
                "text/plain",
            )
        },
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]
    client.post(f"/api/profiles/{profile_id}/confirm").raise_for_status()
    client.post(
        f"/api/profiles/{profile_id}/cloud-consent",
        json={"granted": True, "purposes": ["document_generation"]},
    ).raise_for_status()
    job = client.app.state.store.save_job(_job())
    run = client.app.state.store.save_search(
        SearchRecord(
            status=SearchStatus.COMPLETED,
            request={"flow": "simple_search"},
            result={"jobs": [{"job_id": job.job_id}]},
        )
    )
    saved = client.post(
        "/api/saved-jobs",
        json={"job_id": job.job_id, "search_id": run.search_id},
    )
    saved.raise_for_status()
    saved_id = saved.json()["saved_id"]

    started = client.post(
        f"/api/saved-jobs/{saved_id}/interview-guides",
        params={"profile_id": profile_id},
        headers={"Idempotency-Key": "guide-modern-happy-path"},
    )
    assert started.status_code == 202, started.text

    deadline = time.monotonic() + 8
    guide = started.json()
    while guide["status"] in {"preparing", "reviewing", "rendering"}:
        assert time.monotonic() < deadline, guide
        time.sleep(0.03)
        current = client.get(
            f"/api/saved-jobs/{saved_id}/interview-guides/{profile_id}"
        )
        current.raise_for_status()
        guide = current.json()

    assert guide["status"] == "ready", guide
    assert guide["document_id"]
    downloaded = client.get(
        f"/api/saved-jobs/{saved_id}/interview-guides/{profile_id}/document.pdf"
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content.startswith(b"%PDF")


def test_linkedin_imports_and_optimization_versions_survive_reload(client) -> None:
    imported = client.post(
        "/api/profiles/import",
        params={"language": "en"},
        files={
            "file": (
                "resume.txt",
                b"Built Playwright regression tests for Acme in 2025.",
                "text/plain",
            )
        },
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]
    client.post(f"/api/profiles/{profile_id}/confirm").raise_for_status()
    client.post(
        f"/api/profiles/{profile_id}/cloud-consent",
        json={"granted": True, "purposes": ["document_generation"]},
    ).raise_for_status()
    client.app.state.ai_client = DocumentRegistry()
    snapshot = client.post(
        "/api/linkedin/imports",
        json={
            "profile_id": profile_id,
            "language": "en",
            "target_roles": ["QA Engineer"],
            "text": "Headline\nQA Engineer\nAbout\nPlaywright regression testing",
        },
    )
    snapshot.raise_for_status()
    snapshot_id = snapshot.json()["snapshot_id"]
    optimized = client.post(
        f"/api/linkedin/imports/{snapshot_id}/optimize",
        json={"target_roles": ["QA Engineer"], "language": "es-CR"},
    )
    optimized.raise_for_status()
    assert optimized.json()["language"] == "es-CR"

    imports = client.get("/api/linkedin/imports", params={"profile_id": profile_id})
    versions = client.get(f"/api/linkedin/imports/{snapshot_id}/optimizations")

    assert imports.status_code == versions.status_code == 200
    assert [item["snapshot_id"] for item in imports.json()] == [snapshot_id]
    assert imports.json()[0]["language"] == "es-CR"
    assert versions.json()[0]["optimization_id"] == optimized.json()["optimization_id"]

    settings = Settings(
        data_dir=client.app.state.settings.data_dir,
        database_path=client.app.state.settings.database_path,
    )
    with TestClient(create_app(settings=settings)) as restarted:
        restarted.get("/api/session").raise_for_status()
        restored_imports = restarted.get(
            "/api/linkedin/imports", params={"profile_id": profile_id}
        )
        restored_versions = restarted.get(
            f"/api/linkedin/imports/{snapshot_id}/optimizations"
        )

    assert restored_imports.status_code == restored_versions.status_code == 200
    assert restored_imports.json()[0]["snapshot_id"] == snapshot_id
    assert (
        restored_versions.json()[0]["optimization_id"]
        == optimized.json()["optimization_id"]
    )


def test_linkedin_pdf_upload_is_accepted(client) -> None:
    imported = client.post(
        "/api/profiles/import",
        params={"language": "en"},
        files={
            "file": (
                "resume.txt",
                b"Built Playwright regression tests for Acme in 2025.",
                "text/plain",
            )
        },
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]

    pdf_buffer = BytesIO()
    pdf = Canvas(pdf_buffer)
    pdf.drawString(72, 740, "Headline")
    pdf.drawString(72, 720, "QA Engineer")
    pdf.drawString(72, 690, "About")
    pdf.drawString(72, 670, "Quality engineer focused on reliable releases.")
    pdf.save()

    response = client.post(
        "/api/linkedin/imports",
        data={"profile_id": profile_id, "language": "en"},
        files={"file": ("linkedin.pdf", pdf_buffer.getvalue(), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["source_filename"] == "linkedin.pdf"
    assert response.json()["sections"]["headline"] == "QA Engineer"
    assert "Quality engineer focused" in response.json()["source_text"]


def test_existing_linkedin_import_can_be_reparsed_locally(client) -> None:
    imported = client.post(
        "/api/profiles/import",
        params={"language": "en"},
        files={"file": ("resume.txt", b"QA Engineer with Playwright.", "text/plain")},
    )
    imported.raise_for_status()
    profile_id = imported.json()["profile"]["profile_id"]
    snapshot = client.post(
        "/api/linkedin/imports",
        json={
            "profile_id": profile_id,
            "language": "en",
            "target_roles": ["QA Engineer"],
            "text": (
                "Kendall Valverde\nQA Engineer\nAbout\n"
                "Quality engineer focused on reliable releases.\n"
                "Top Skills\nPlaywright\nSelenium"
            ),
        },
    )
    snapshot.raise_for_status()

    reparsed = client.post(
        f"/api/linkedin/imports/{snapshot.json()['snapshot_id']}/reparse"
    )

    assert reparsed.status_code == 200, reparsed.text
    assert reparsed.json()["sections"]["headline"] == "QA Engineer"
    assert "reliable releases" in reparsed.json()["sections"]["about"]
    assert "Playwright" in reparsed.json()["sections"]["skills"]
