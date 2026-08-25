import io
import time
import zipfile
from pathlib import Path

from conftest import wait_for_run
from fastapi.testclient import TestClient
from job_orchestrator.api import create_app
from job_orchestrator.config import Settings


def test_replay_end_to_end_without_network_or_deepseek(
    client: TestClient,
    monkeypatch,
) -> None:
    status_history: dict[str, list[str]] = {}
    original_save_job = client.app.state.store.save_job

    def record_status(job):
        status_history.setdefault(job.job_id, []).append(str(job.pipeline_status))
        return original_save_job(job)

    monkeypatch.setattr(client.app.state.store, "save_job", record_status)
    response = client.post(
        "/runs", json={"mode": "replay", "query": "python", "auto_approve": True}
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    run = wait_for_run(client, run_id)
    assert run["status"] == "completed", run

    events = client.get(f"/runs/{run_id}/events").json()
    assert events[0]["type"] == "run_started"
    assert events[-1]["type"] == "run_completed"
    assert {event["actor_id"] for event in events} >= {
        "career_coordinator",
        "opportunity_scout",
        "fit_analyst",
        "application_tailor",
        "quality_reviewer",
    }
    assert all(event["ui"]["template_key"] for event in events)

    final_statuses = {
        item["job"]["job_id"]: item["job"]["pipeline_status"]
        for item in run["result"]["ranked_jobs"]
    }
    assert set(final_statuses.values()) == {"approved", "analyzed"}
    for job_id, final_status in final_statuses.items():
        history = status_history[job_id]
        if final_status == "approved":
            expected = [
                "eligible",
                "shortlisted",
                "drafting",
                "reviewing",
                "ready_for_approval",
                "approved",
            ]
            assert [history.index(status) for status in expected] == sorted(
                history.index(status) for status in expected
            )
        else:
            assert "analyzed" in history
            assert "shortlisted" not in history

    artifacts = client.get(f"/runs/{run_id}/artifacts").json()
    assert artifacts


def test_sse_replays_persisted_events(client: TestClient) -> None:
    run_id = client.post(
        "/runs", json={"mode": "replay", "auto_approve": True}
    ).json()["run_id"]
    wait_for_run(client, run_id)
    with client.stream("GET", f"/runs/{run_id}/events/stream") as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "event: run_started" in body
    assert "event: run_completed" in body


def test_manual_profile_job_and_ranking(client: TestClient) -> None:
    profile = client.post(
        "/profiles",
        json={
            "name": "Ada",
            "summary": "Python SQL",
            "facts": [{"category": "skill", "text": "Python SQL APIs", "verified": True}],
            "preferences": {"keywords": ["Python"], "remote_required": True},
        },
    ).json()
    job = client.post(
        "/jobs/manual",
        json={
            "title": "Python Engineer",
            "company": "Acme",
            "description": "Build Python APIs with SQL",
            "remote": True,
            "url": "https://jobs.example.test/python-engineer",
            "posted_at": "2026-08-20T00:00:00Z",
        },
    ).json()
    response = client.post(
        "/ranking", json={"profile_id": profile["profile_id"], "job_ids": [job["job_id"]]}
    )
    assert response.status_code == 200
    assert response.json()[0]["eligible"] is True


def test_api_contract_is_session_guarded_and_replayable(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/search-runs").status_code == 401
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json() == {"status": "ready"}
    assert client.cookies.get("job_orchestrator_session")

    response = client.post(
        "/api/search-runs", json={"mode": "replay", "auto_approve": True}
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    wait_for_run(client, run_id)
    with client.stream(
        "GET",
        f"/api/runs/{run_id}/events",
        params={"after_sequence": 1},
        headers={"Last-Event-ID": "1"},
    ) as stream:
        body = "".join(stream.iter_text())
    assert "event: run_completed" in body
    assert "id: 1\n" not in body


def test_expected_frontend_paths_are_exposed(client: TestClient) -> None:
    client.get("/api/session")
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/profiles/import" in paths
    assert "/api/search-runs" in paths
    assert "/api/runs/{run_id}/events" in paths
    assert "/api/runs/{run_id}/cancel" in paths
    assert "/api/approvals/{approval_id}/decisions" in paths
    assert "/api/application-packs/{artifact_id}/export" in paths
    assert "/api/jobs/{job_id}/pipeline-status" in paths


def _wait_for_pending_approval(client: TestClient, run_id: str, kind: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/runs/{run_id}").json()
        approvals = client.get(f"/runs/{run_id}/approvals").json()
        pending = [item for item in approvals if item["status"] == "pending"]
        if run["status"] == "awaiting_user" and pending and pending[-1]["kind"] == kind:
            return pending[-1]
        time.sleep(0.02)
    raise AssertionError(f"Pending approval {kind} did not appear")


def test_interactive_replay_requires_all_three_human_gates(client: TestClient) -> None:
    run_id = client.post(
        "/api/search-runs",
        json={"mode": "replay", "auto_approve": False, "query": "python"},
    ).json()["run_id"]
    decisions = [
        ("profile_confirmation", "approve"),
        ("shortlist_selection", "select"),
        ("application_approval", "approve"),
    ]
    for kind, decision in decisions:
        approval = _wait_for_pending_approval(client, run_id, kind)
        response = client.post(
            f"/api/approvals/{approval['approval_id']}/decisions",
            json={
                "decision": decision,
                "entity_ids": approval["payload"].get("entity_ids", []),
                "artifact_version": approval.get("artifact_version"),
            },
        )
        assert response.status_code == 200, response.text
    run = wait_for_run(client, run_id)
    assert run["status"] == "completed"
    assert len(client.get(f"/runs/{run_id}/approvals").json()) == 3


def test_second_decision_on_same_gate_returns_conflict(client: TestClient) -> None:
    run_id = client.post(
        "/api/search-runs", json={"mode": "replay", "auto_approve": False}
    ).json()["run_id"]
    approval = _wait_for_pending_approval(
        client, run_id, "profile_confirmation"
    )
    path = f"/api/approvals/{approval['approval_id']}/decisions"
    decision = {
        "decision": "approve",
        "entity_ids": approval["payload"]["entity_ids"],
    }
    assert client.post(path, json=decision).status_code == 200
    assert client.post(path, json=decision).status_code == 409


def test_shortlist_decision_accepts_only_offered_jobs_and_at_most_three(
    client: TestClient,
) -> None:
    run_id = client.post(
        "/api/search-runs", json={"mode": "replay", "auto_approve": False}
    ).json()["run_id"]
    profile_gate = _wait_for_pending_approval(
        client, run_id, "profile_confirmation"
    )
    client.post(
        f"/api/approvals/{profile_gate['approval_id']}/decisions",
        json={"decision": "approve"},
    ).raise_for_status()
    shortlist = _wait_for_pending_approval(
        client, run_id, "shortlist_selection"
    )
    path = f"/api/approvals/{shortlist['approval_id']}/decisions"
    offered = shortlist["offered_entity_ids"]
    assert client.post(
        path,
        json={"decision": "select", "entity_ids": [*offered, "job_not_offered"]},
    ).status_code == 422
    assert client.post(
        path,
        json={"decision": "select", "entity_ids": ["job_not_offered"]},
    ).status_code == 422
    assert client.get(f"/runs/{run_id}/approvals").json()[-1]["status"] == "pending"


def test_export_contains_four_pdf_documents(client: TestClient) -> None:
    run_id = client.post(
        "/api/search-runs", json={"mode": "replay", "auto_approve": True}
    ).json()["run_id"]
    wait_for_run(client, run_id)
    artifact = client.get(f"/runs/{run_id}/artifacts").json()[0]
    prepared = client.post(
        f"/api/application-packs/{artifact['artifact_id']}/export"
    )
    assert prepared.status_code == 200, prepared.text
    assert set(prepared.json()["files"]) == {
        "cv_ats.pdf",
        "cv_styled.pdf",
        "application_brief.pdf",
        "cover_letter.pdf",
    }
    downloaded = client.get(prepared.json()["download_url"])
    assert downloaded.status_code == 200
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert set(archive.namelist()) == set(prepared.json()["files"])


def test_replay_pending_gate_recovers_without_duplicate_approval(
    tmp_path: Path,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "replay-restart.sqlite3",
        replay_delay_ms=0,
        session_token="replay-restart-token",
    )
    with TestClient(create_app(settings=settings)) as first:
        first.get("/api/session").raise_for_status()
        response = first.post(
            "/api/search-runs", json={"mode": "replay", "auto_approve": False}
        )
        response.raise_for_status()
        run_id = response.json()["run_id"]
        original = _wait_for_pending_approval(
            first, run_id, "profile_confirmation"
        )

    with TestClient(create_app(settings=settings)) as second:
        second.get("/api/session").raise_for_status()
        recovered = _wait_for_pending_approval(
            second, run_id, "profile_confirmation"
        )
        assert recovered["approval_id"] == original["approval_id"]
        response = second.post(
            f"/api/approvals/{recovered['approval_id']}/decisions",
            json={"decision": "approve", "entity_ids": recovered["payload"]["entity_ids"]},
        )
        response.raise_for_status()
        next_gate = _wait_for_pending_approval(
            second, run_id, "shortlist_selection"
        )
        assert next_gate["approval_id"] != original["approval_id"]
        approvals = second.get(f"/runs/{run_id}/approvals").json()
        assert len(approvals) == 2
