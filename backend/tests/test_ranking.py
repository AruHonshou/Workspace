from job_orchestrator.ranking import deduplicate_jobs, normalize_manual_job, rank_job
from job_orchestrator.schemas import (
    ManualJobCreate,
    Profile,
    ProfileFact,
    UserPreferences,
)


def test_ranking_is_deterministic_and_respects_remote_gate() -> None:
    profile = Profile(
        name="Ada",
        summary="Python and SQL engineer",
        facts=[
            ProfileFact(
                category="skill", text="Built Python APIs with SQL", verified=True
            )
        ],
        preferences=UserPreferences(keywords=["Python", "SQL"], remote_required=True),
    )
    job = normalize_manual_job(
        ManualJobCreate(
            title="Python Engineer",
            company="Acme",
            description="Python SQL APIs",
            remote=False,
        )
    )
    result = rank_job(job, profile)
    assert result.eligible is False
    assert result.score == rank_job(job, profile).score


def test_deduplicate_jobs() -> None:
    payload = ManualJobCreate(
        title="Engineer", company="Acme", description="Build things"
    )
    assert (
        len(
            deduplicate_jobs(
                [normalize_manual_job(payload), normalize_manual_job(payload)]
            )
        )
        == 1
    )


def test_unknown_constraints_warn_without_rejecting() -> None:
    profile = Profile(
        name="Ada",
        facts=[ProfileFact(category="skill", text="Built Python APIs", verified=True)],
        preferences=UserPreferences(
            minimum_salary=80_000,
            currency="USD",
            work_authorization="Costa Rica",
        ),
    )
    job = normalize_manual_job(
        ManualJobCreate(
            title="Python Engineer",
            company="Acme",
            description="Build Python APIs",
        )
    )
    result = rank_job(job, profile)
    statuses = {criterion.name: criterion.status for criterion in result.criteria}
    assert result.eligible is None
    assert statuses["salary_floor"] == "unknown"
    assert statuses["work_authorization"] == "unknown"
