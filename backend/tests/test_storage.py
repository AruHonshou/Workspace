from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from job_orchestrator.ranking import normalize_manual_job
from job_orchestrator.schemas import (
    Approval,
    ApprovalKind,
    ApprovalStatus,
    Artifact,
    EventUI,
    GraphEvent,
    ManualJobCreate,
    Profile,
    Run,
    RunStatus,
    utc_now,
)
from job_orchestrator.storage import SQLiteStore


def test_migration_and_round_trip(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    profile = store.save_profile(Profile(name="Ada"))
    job = store.save_job(
        normalize_manual_job(
            ManualJobCreate(title="Python Engineer", company="Acme", description="Build APIs")
        )
    )
    run = store.save_run(Run(profile_id=profile.profile_id))
    event = store.append_event(
        GraphEvent(
            run_id=run.run_id,
            sequence=1,
            type="run_started",
            stage="profile",
            visibility="user",
            ui=EventUI(template_key="run.started"),
        )
    )

    assert store.get_profile(profile.profile_id) == profile
    assert store.get_job(job.job_id) == job
    assert store.get_run(run.run_id).run_id == run.run_id
    assert store.list_events(run.run_id)[0] == event


def test_job_deduplicates_by_content(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    payload = ManualJobCreate(title="Engineer", company="A", description="Same description")
    first = store.save_job(normalize_manual_job(payload))
    second = store.save_job(normalize_manual_job(payload))
    assert first.job_id == second.job_id
    assert len(store.list_jobs()) == 1
    assert [item.job_id for item in store.search_jobs_text("Engineer Same")] == [
        first.job_id
    ]


def test_event_sequence_and_cancellation_are_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    run = store.save_run(Run(status=RunStatus.RUNNING))
    for event_type in ("first", "second"):
        store.append_event(
            GraphEvent(
                run_id=run.run_id,
                sequence=99,
                type=event_type,
                stage="test",
                visibility="user",
                ui=EventUI(template_key=f"event.{event_type}"),
            )
        )
    assert [event.sequence for event in store.list_events(run.run_id)] == [1, 2]
    first, changed = store.cancel_run_once(run.run_id)
    second, changed_again = store.cancel_run_once(run.run_id)
    assert first is not None and first.status == RunStatus.CANCELLED
    assert second is not None and second.status == RunStatus.CANCELLED
    assert changed is True
    assert changed_again is False


def test_legacy_avatar_animation_cue_is_ignored() -> None:
    event = GraphEvent.model_validate(
        {
            "run_id": "run_legacy",
            "sequence": 1,
            "type": "agent_started",
            "stage": "search",
            "visibility": "user",
            "ui": {
                "template_key": "career.search.started",
                "animation_cue": None,
            },
        }
    )
    assert "animation_cue" not in event.ui.model_dump()


def test_stale_run_save_cannot_reverse_cancellation(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    run = store.save_run(Run(status=RunStatus.RUNNING))
    stale = store.get_run(run.run_id)
    assert stale is not None

    cancelled, changed = store.cancel_run_once(run.run_id)
    assert cancelled is not None and changed is True
    stale.status = RunStatus.COMPLETED

    assert store.save_run_if_not_terminal(stale) is None
    persisted = store.get_run(run.run_id)
    assert persisted is not None
    assert persisted.status == RunStatus.CANCELLED


def test_cancelled_run_rejects_new_artifact(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    profile = store.save_profile(Profile(name="Ada"))
    job = store.save_job(
        normalize_manual_job(
            ManualJobCreate(title="Engineer", company="A", description="Build APIs")
        )
    )
    run = store.save_run(Run(profile_id=profile.profile_id, status=RunStatus.RUNNING))
    store.cancel_run_once(run.run_id)
    artifact = Artifact(
        run_id=run.run_id,
        job_id=job.job_id,
        profile_id=profile.profile_id,
        kind="application_brief",
        title="Late artifact",
        content="This must not be stored after cancellation.",
    )

    assert store.save_artifact_if_run_active(artifact) is None
    assert store.get_artifact(artifact.artifact_id) is None


def test_artifact_versions_are_scoped_to_each_run(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    profile = store.save_profile(Profile(name="Ada"))
    job = store.save_job(
        normalize_manual_job(
            ManualJobCreate(title="Engineer", company="A", description="Build APIs")
        )
    )
    first_run = store.save_run(Run(profile_id=profile.profile_id))
    second_run = store.save_run(Run(profile_id=profile.profile_id))
    first = store.save_artifact(
        Artifact(
            run_id=first_run.run_id,
            job_id=job.job_id,
            profile_id=profile.profile_id,
            kind="application_brief",
            title="First",
            content="First run",
            version=1,
        )
    )
    second = store.save_artifact(
        Artifact(
            run_id=second_run.run_id,
            job_id=job.job_id,
            profile_id=profile.profile_id,
            kind="application_brief",
            title="Second",
            content="Second run",
            version=1,
        )
    )
    assert first.artifact_id != second.artifact_id
    assert store.list_artifacts(first_run.run_id) == [first]
    assert store.list_artifacts(second_run.run_id) == [second]


def test_approval_resolution_compare_and_swap_is_atomic(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "store.sqlite3")
    store.migrate()
    run = store.save_run(Run())
    approval = store.save_approval(
        Approval(
            run_id=run.run_id,
            kind=ApprovalKind.PROFILE_CONFIRMATION,
            allowed_decisions=["approve", "reject"],
        )
    )
    barrier = Barrier(2)

    def resolve(status: ApprovalStatus):
        candidate = store.get_approval(approval.approval_id)
        assert candidate is not None
        candidate.status = status
        candidate.resolved_at = utc_now()
        barrier.wait()
        return store.resolve_approval(candidate)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(resolve, [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED])
        )
    assert sum(item is not None for item in results) == 1
    assert store.get_approval(approval.approval_id).status in {
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
    }
