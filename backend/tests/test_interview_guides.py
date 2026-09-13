from datetime import timedelta
from pathlib import Path

import pytest
from job_orchestrator.api import _normalize_generated_guide_content
from job_orchestrator.career import build_interview_guide
from job_orchestrator.documents import (
    _validate_interview_guide_artifact,
    render_artifact_pdf,
)
from job_orchestrator.schemas import (
    Artifact,
    DeepFitAnalysis,
    InterviewGuide,
    JobRecord,
    Profile,
    ProfileFact,
    SourceKind,
    utc_now,
)
from pypdf import PdfReader


def _qa_guide_fixture(language: str) -> tuple[InterviewGuide, JobRecord, Profile]:
    spanish = language == "es"
    playwright_fact = ProfileFact(
        fact_id=f"fact_playwright_{language}",
        category="experience",
        text=(
            "Automaticé flujos críticos con Playwright y TypeScript, incluyendo trazas de diagnóstico."
            if spanish
            else "Automated critical flows with Playwright and TypeScript, including diagnostic traces."
        ),
        language=language,
        verified=True,
    )
    api_fact = ProfileFact(
        fact_id=f"fact_api_{language}",
        category="experience",
        text=(
            "Validé contratos y reglas de negocio de APIs REST con Postman y consultas SQL."
            if spanish
            else "Validated REST API contracts and business rules with Postman and SQL queries."
        ),
        language=language,
        verified=True,
    )
    unrelated_fact = ProfileFact(
        fact_id=f"fact_unrelated_{language}",
        category="experience",
        text=(
            "Coordiné el inventario físico de una oficina durante una mudanza interna."
            if spanish
            else "Coordinated the physical office inventory during an internal move."
        ),
        language=language,
        verified=True,
    )
    other_language_fact = ProfileFact(
        fact_id="fact_other_language",
        category="experience",
        text="This fact belongs to the other resume and must never appear in this guide.",
        language="en" if spanish else "es",
        verified=True,
    )
    profile = Profile(
        name="Perfil QA",
        facts=[playwright_fact, api_fact, unrelated_fact, other_language_fact],
        confirmed=True,
    )
    requirements = (
        [
            "Experiencia con Playwright y TypeScript para automatización web.",
            "Experiencia validando APIs REST con Postman y SQL.",
            "Experiencia en pruebas manuales y documentación de defectos.",
        ]
        if spanish
        else [
            "Experience with Playwright and TypeScript for web automation.",
            "Experience validating REST APIs with Postman and SQL.",
            "Experience in manual testing and defect documentation.",
        ]
    )
    job = JobRecord(
        source=SourceKind.MANUAL,
        external_id=f"qa-guide-{language}",
        title="Ingeniero QA" if spanish else "QA Engineer",
        company="Quality Garden",
        location="San José, Costa Rica",
        remote=True,
        description=(
            "El puesto asegura la calidad de una plataforma web. Requiere diseñar pruebas, "
            "automatizar escenarios con Playwright, validar APIs y comunicar defectos con claridad."
            if spanish
            else "The role protects the quality of a web platform. It requires test design, "
            "Playwright automation, API validation, and clear defect communication."
        ),
        requirements=requirements,
        preferred_requirements=[
            "Conocimiento de integración continua."
            if spanish
            else "Knowledge of continuous integration."
        ],
        url=f"https://careers.example.test/qa-{language}",
        final_url=f"https://careers.example.test/qa-{language}",
        posted_at=utc_now() - timedelta(hours=4),
        date_confidence="exact",
        official_url_verified=True,
    )
    analysis = DeepFitAnalysis(
        job_id=job.job_id,
        profile_id=profile.profile_id,
        score=72,
        level="high",
        resume_language=language,
        matched_requirements=[
            {
                "requirement": requirements[0],
                "fact_id": playwright_fact.fact_id,
                "evidence": "UNTRUSTED ANALYSIS EVIDENCE MUST NOT BE USED",
            },
            {
                "requirement": requirements[1],
                "fact_id": api_fact.fact_id,
                "evidence": "ANOTHER UNTRUSTED CLAIM",
            },
        ],
        missing_requirements=[requirements[2]],
    )
    guide = InterviewGuide(
        saved_id="saved_qa",
        profile_id=profile.profile_id,
        job_id=job.job_id,
        search_id="search_qa",
        job_title=job.title,
        company=job.company,
        apply_url=job.url,
        published_at=job.posted_at,
        analysis=analysis,
        language=language,
    )
    return guide, job, profile


@pytest.mark.parametrize("language", ["es", "en"])
def test_professional_interview_guide_is_complete_grounded_and_renderable(
    tmp_path: Path, language: str
) -> None:
    guide, job, profile = _qa_guide_fixture(language)
    artifact = build_interview_guide(guide=guide, job=job, profile=profile)

    question_label = (
        "### Pregunta técnica" if language == "es" else "### Technical question"
    )
    reference_label = (
        "Respuesta técnica de referencia"
        if language == "es"
        else "Technical reference answer"
    )
    employer_section = (
        "## 6. Preguntas para la empresa"
        if language == "es"
        else "## 6. Questions for the employer"
    )
    assert artifact.content.count(question_label) == 10
    assert reference_label in artifact.content
    assert employer_section in artifact.content
    assert "Playwright" in artifact.content
    assert "fact_playwright" not in artifact.content
    assert "[fact_id:" not in artifact.content
    assert "STAR" not in artifact.content
    assert "UNTRUSTED ANALYSIS EVIDENCE" not in artifact.content
    assert "fact_other_language" not in artifact.content
    unrelated_text = (
        "Coordiné el inventario físico de una oficina durante una mudanza interna."
        if language == "es"
        else "Coordinated the physical office inventory during an internal move."
    )
    assert unrelated_text not in artifact.content
    assert {claim.fact_ids[0] for claim in artifact.claims} == {
        f"fact_playwright_{language}",
        f"fact_api_{language}",
    }

    path = render_artifact_pdf(artifact, tmp_path / f"qa-guide-{language}.pdf")
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert 8 <= len(reader.pages) <= 20
    assert job.title in text
    assert reference_label in text
    assert "Playwright" in text
    assert "[fact_id:" not in text
    assert "STAR" not in text
    assert all((page.extract_text() or "").strip() for page in reader.pages)
    assert any(
        annotation.get_object().get("/Subtype") == "/Link"
        for page in reader.pages
        for annotation in page.get("/Annots", [])
    )


def test_interview_guide_renderer_rejects_an_unsupported_fact_reference(
    tmp_path: Path,
) -> None:
    guide, job, profile = _qa_guide_fixture("en")
    artifact = build_interview_guide(guide=guide, job=job, profile=profile)
    poisoned = artifact.model_copy(
        update={
            "content": f"{artifact.content}\nConfirmed evidence: invented [fact_id: forged]"
        }
    )

    with pytest.raises(ValueError, match="must not expose internal fact identifiers"):
        render_artifact_pdf(poisoned, tmp_path / "poisoned.pdf")


def test_model_guide_accepts_equivalent_section_headings() -> None:
    sections = [
        "## 1. Role Overview",
        "## 2. Key Responsibilities",
        "## 3. Requirement and Evidence Matrix",
        "## 4. Real Gaps",
        "## 5. Technical Interview Questions and Reference Answers",
        "## 6. Practical Exercises",
        "## 7. Questions for the Employer and Study Plan",
    ]
    questions = [
        (
            f"**Technical Question {index}: How would you approach scenario {index}?**\n"
            "Explain the trade-offs, validation strategy, expected evidence, and a "
            "clear technical reference answer grounded in the vacancy requirements."
        )
        for index in range(1, 9)
    ]
    artifact = Artifact(
        run_id="guide_heading_test",
        job_id="job_heading_test",
        profile_id="profile_heading_test",
        kind="interview_guide",
        title="Interview guide",
        language="en",
        content="\n\n".join([*sections, *questions]),
    )

    _validate_interview_guide_artifact(artifact)


def test_model_guide_removes_internal_ids_and_restores_verified_source() -> None:
    _guide, job, _profile = _qa_guide_fixture("en")
    content = (
        "## Requirement matrix\n"
        "| Requirement | Evidence | Assessment |\n"
        "| --- | --- | --- |\n"
        "| Playwright | fact_internal_123 (confirmed evidence) | Supported |\n"
        "Job Requirement | Candidate Evidence (Fact ID)\n"
        "API testing | about_internal_456 Postman (facts fact_a, fact_b, )\n"
        "## Source\nSource date: 2020-01-01.\n"
        "URL: https://stale.example.test/job."
    )

    normalized = _normalize_generated_guide_content(
        content,
        job=job,
        language="en",
    )

    assert "fact_internal_123" not in normalized
    assert "about_internal_456" not in normalized
    assert "Fact ID" not in normalized
    assert "(facts" not in normalized
    assert "| Requirement |" not in normalized
    assert "API testing: Postman" in normalized
    assert str(job.url) in normalized
    assert job.posted_at.isoformat() in normalized
    assert "stale.example.test" not in normalized
    assert normalized.count("## Verified publication information") == 1
