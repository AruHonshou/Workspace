from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from job_orchestrator.ranking import normalize_manual_job
from job_orchestrator.schemas import (
    ATSResumeVersion,
    DeepFitAnalysis,
    InterviewGuide,
    ManualJobCreate,
    Profile,
    ProfileFact,
    ProfileUpdate,
    ResumeDocument,
    SavedJob,
    UserPreferences,
    utc_now,
)
from job_orchestrator.storage import ProfileDisplayNameConflictError, SQLiteStore


def test_profile_contract_normalizes_preferences_and_validates_filters() -> None:
    profile = Profile.model_validate(
        {
            "name": "Ada",
            "preferences": {
                "keywords": [" Python ", "python", "SQL"],
                "desired_locations": ["Costa Rica"],
                "remote_required": True,
                "target_seniorities": ["junior", "junior", "mid"],
                "allowed_work_modes": ["remote", "hybrid"],
                "excluded_sectors": [" Gambling ", "gambling"],
            },
        }
    )
    assert profile.display_name == "Perfil actual"
    assert profile.preferences.keywords == ["Python", "SQL"]
    assert profile.preferences.target_seniorities == ["junior", "mid"]
    assert profile.preferences.excluded_sectors == ["Gambling"]
    with pytest.raises(ValidationError):
        UserPreferences(target_seniorities=["wizard"])
    with pytest.raises(ValidationError):
        UserPreferences(allowed_work_modes=["teleport"])


def test_update_and_duplicate_profiles_are_revisioned_and_independent(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    document = ResumeDocument(
        document_id="document_original",
        language="es",
        filename="cv-es.pdf",
        text="Experiencia en QA",
        extraction_method="text",
    )
    source = store.save_profile(
        Profile(
            display_name="QA",
            name="Ada",
            confirmed=True,
            facts=[ProfileFact(category="skill", text="Playwright", verified=True)],
            resumes={"es": document},
        )
    )
    other = store.save_profile(Profile(display_name="Datos", name="Lin"))
    updated = store.update_profile(
        source.profile_id,
        ProfileUpdate(
            display_name="QA Automation",
            preferences=UserPreferences(
                keywords=["Playwright"],
                desired_locations=["Costa Rica"],
                excluded_sectors=["gambling"],
            ),
        ),
    )
    assert updated is not None
    assert updated.display_name == "QA Automation"
    assert updated.revision == source.revision + 1
    with pytest.raises(ProfileDisplayNameConflictError):
        store.rename_profile(updated.profile_id, " datos ")
    duplicate = store.duplicate_profile(updated.profile_id)
    assert duplicate is not None
    assert duplicate.profile_id != updated.profile_id
    assert duplicate.facts[0].fact_id != updated.facts[0].fact_id
    assert duplicate.resumes["es"].document_id != updated.resumes["es"].document_id
    assert store.list_interview_guides() == []
    assert store.get_profile(other.profile_id) == other


def test_delete_profile_cascades_modern_documents_but_preserves_shared_job(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    profile = store.save_profile(Profile(display_name="QA", name="Ada"))
    job = store.save_job(
        normalize_manual_job(
            ManualJobCreate(
                title="QA Engineer",
                company="Acme",
                description="Test APIs with Python.",
                url="https://jobs.example.test/qa",
                posted_at=utc_now(),
            )
        )
    )
    saved = store.save_saved_job(
        SavedJob(
            job_id=job.job_id,
            search_id="search_test",
            title=job.title,
            company=job.company,
            apply_url=job.url,
            published_at=job.posted_at,
        )
    )
    guide = store.save_interview_guide(
        InterviewGuide(
            saved_id=saved.saved_id,
            profile_id=profile.profile_id,
            job_id=job.job_id,
            search_id=saved.search_id,
            job_title=job.title,
            company=job.company,
            apply_url=job.url,
            published_at=job.posted_at,
            analysis=DeepFitAnalysis(
                job_id=job.job_id, profile_id=profile.profile_id, score=80, level="high"
            ),
            language="en",
            status="ready",
        )
    )
    resume = store.save_ats_resume_version(
        ATSResumeVersion(
            resume_id="ats_profile_delete",
            saved_id=saved.saved_id,
            version=1,
            profile_id=profile.profile_id,
            profile_revision=profile.revision,
            job_id=job.job_id,
            job_content_hash=job.content_hash,
            status="ready",
        )
    )
    assert store.delete_profile(profile.profile_id) is True
    assert store.get_profile(profile.profile_id) is None
    assert store.get_interview_guide(guide.guide_id) is None
    assert store.get_ats_resume_version(resume.version_id) is None
    assert store.get_job(job.job_id) is not None
