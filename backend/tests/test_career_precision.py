from job_orchestrator.career import build_deep_analysis_v2, extract_requirements
from job_orchestrator.schemas import (
    JobRecord,
    Profile,
    ProfileFact,
    SourceKind,
    utc_now,
)


def _job(description: str) -> JobRecord:
    return JobRecord(
        source=SourceKind.MANUAL,
        external_id="precision-job",
        title="Digital Quality Assurance",
        company="Example",
        location="Costa Rica",
        url="https://jobs.example.test/precision",
        posted_at=utc_now(),
        description=description,
    )


def test_requirement_extraction_discards_marketing_and_benefit_sentences() -> None:
    job = _job(
        "This is an excellent opportunity to work with industry-leading tools while "
        "building technical and marketing skills in a fast-paced environment. "
        "Minimum qualification: Bachelor's degree and/or 4 years related experience "
        "in software quality assurance. Experience with web analytics implementation "
        "and debugging is preferred. También te proporcionaremos: una experiencia de "
        "incorporación atractiva y beneficios competitivos."
    )

    requirements = extract_requirements(job)

    assert len(requirements) == 2
    assert any("Bachelor's degree" in value for value in requirements)
    assert any("web analytics" in value for value in requirements)
    assert all("excellent opportunity" not in value for value in requirements)
    assert all("proporcionaremos" not in value for value in requirements)


def test_analysis_does_not_use_generic_qa_evidence_for_adobe_requirements() -> None:
    job = _job(
        "Experience with Adobe Analytics, Adobe Experience Manager and Adobe Journey "
        "Optimizer is required. Experience with QA platforms such as Jira, Confluence "
        "and Tosca is a plus."
    )
    profile = Profile(
        name="QA",
        confirmed=True,
        facts=[
            ProfileFact(
                category="experience",
                language="en",
                text="QA Engineer with banking experience across manual, API and automated testing.",
                verified=True,
            ),
            ProfileFact(
                category="experience",
                language="en",
                text="Managed defects and QA-to-development traceability in Jira.",
                verified=True,
            ),
        ],
    )

    analysis = build_deep_analysis_v2(job, profile)

    adobe = next(
        item for item in analysis.requirement_analysis if "Adobe Analytics" in item.requirement
    )
    platforms = next(
        item for item in analysis.requirement_analysis if "Jira" in item.requirement
    )
    assert adobe.status == "gap"
    assert adobe.fact_ids == []
    assert platforms.status == "unknown"
    assert platforms.fact_ids
    assert platforms.requirement in analysis.uncertainties


def test_degree_or_experience_requirement_accepts_confirmed_degree() -> None:
    job = _job(
        "Bachelor's degree and/or 4 years related experience in software quality assurance is required."
    )
    education = ProfileFact(
        category="education",
        language="en",
        text="Bachelor's Degree in Information Systems Engineering.",
        verified=True,
    )
    profile = Profile(name="QA", confirmed=True, facts=[education])

    analysis = build_deep_analysis_v2(job, profile)

    assert analysis.requirement_analysis[0].status == "supported"
    assert analysis.requirement_analysis[0].fact_ids == [education.fact_id]
