from __future__ import annotations

import time
from pathlib import Path

from conftest import wait_for_run
from fastapi.testclient import TestClient
from job_orchestrator.api import create_app
from job_orchestrator.config import Settings
from job_orchestrator.schemas import Run, RunStatus


def _pending(client: TestClient, run_id: str, kind: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        approvals = client.get(f"/runs/{run_id}/approvals").json()
        matching = [
            item
            for item in approvals
            if item["status"] == "pending" and item["kind"] == kind
        ]
        if matching:
            return matching[-1]
        time.sleep(0.02)
    raise AssertionError(f"Pending approval {kind} did not appear")


def _approve(client: TestClient, approval: dict) -> None:
    decision = "select" if approval["kind"] == "shortlist_selection" else "approve"
    response = client.post(
        f"/api/approvals/{approval['approval_id']}/decisions",
        json={
            "decision": decision,
            "entity_ids": approval["payload"].get("entity_ids", []),
            "artifact_version": approval["payload"].get("artifact_version"),
        },
    )
    assert response.status_code == 200, response.text


def _confirmed_profile(client: TestClient) -> dict:
    response = client.post(
        "/profiles",
        json={
            "name": "Ada Local",
            "facts": [
                {
                    "category": "skill",
                    "text": "Built Python APIs and SQL automation.",
                    "verified": True,
                }
            ],
            "preferences": {"keywords": ["Python"], "remote_required": True},
            "confirmed": True,
        },
    )
    response.raise_for_status()
    return response.json()


def test_live_manual_run_uses_same_three_gates_without_network(
    client: TestClient,
    monkeypatch,
) -> None:
    async def network_must_not_run(*_args, **_kwargs):
        raise AssertionError("manual-only live mode attempted a network connector")

    client.app.state.connector_search = network_must_not_run
    profile = _confirmed_profile(client)
    job = client.post(
        "/jobs/manual",
        json={
            "title": "Python Automation Engineer",
            "company": "Local Example",
            "description": "Build Python APIs and SQL automation.",
            "location": "Remote",
            "remote": True,
            "url": "https://jobs.example.test/python-automation",
            "posted_at": "2026-08-20T00:00:00Z",
        },
    ).json()
    status_history: list[str] = []
    original_save_job = client.app.state.store.save_job

    def record_status(saved_job):
        if saved_job.job_id == job["job_id"]:
            status_history.append(str(saved_job.pipeline_status))
        return original_save_job(saved_job)

    monkeypatch.setattr(client.app.state.store, "save_job", record_status)

    response = client.post(
        "/api/search-runs",
        json={
            "mode": "live",
            "profile_id": profile["profile_id"],
            "search": {
                "query": "Python",
                "remote_only": True,
                "sources": ["manual"],
                "limit": 10,
            },
        },
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]

    _approve(client, _pending(client, run_id, "profile_confirmation"))
    shortlist = _pending(client, run_id, "shortlist_selection")
    assert client.get(
        f"/api/jobs/{job['job_id']}/pipeline-status"
    ).json()["status"] == "eligible"
    ranked_at_shortlist = client.get(f"/runs/{run_id}").json()["result"][
        "ranked_jobs"
    ]
    assert ranked_at_shortlist[0]["job"]["pipeline_status"] == "eligible"
    _approve(client, shortlist)

    final_approval = _pending(client, run_id, "application_approval")
    assert client.get(
        f"/api/jobs/{job['job_id']}/pipeline-status"
    ).json()["status"] == "ready_for_approval"
    ranked_at_application_gate = client.get(f"/runs/{run_id}").json()["result"][
        "ranked_jobs"
    ]
    assert (
        ranked_at_application_gate[0]["job"]["pipeline_status"]
        == "ready_for_approval"
    )
    pending_artifact = client.get(f"/runs/{run_id}/artifacts").json()[0]
    export_path = f"/api/application-packs/{pending_artifact['artifact_id']}/export"
    assert client.post(export_path).status_code == 409
    assert client.get(export_path).status_code == 409
    assert client.get(f"/artifacts/{pending_artifact['artifact_id']}.pdf").status_code == 409
    _approve(client, final_approval)

    run = wait_for_run(client, run_id)
    assert run["status"] == "completed", run
    assert run["result"]["job_ids"] == [job["job_id"]]
    assert run["result"]["connector_errors"] == {}
    assert run["result"]["ranked_jobs"][0]["job"]["pipeline_status"] == "approved"
    assert client.get(
        f"/api/jobs/{job['job_id']}/pipeline-status"
    ).json()["status"] == "approved"
    assert client.post(export_path).status_code == 200
    assert status_history.index("eligible") < status_history.index("shortlisted")
    assert status_history.index("shortlisted") < status_history.index("drafting")
    assert status_history.index("drafting") < status_history.index("reviewing")
    assert status_history.index("reviewing") < status_history.index(
        "ready_for_approval"
    )
    assert status_history.index("ready_for_approval") < status_history.index("approved")
    assert status_history.index("approved") < status_history.index("exported")
    fact_id = profile["facts"][0]["fact_id"]
    assert client.patch(
        f"/api/profile-facts/{fact_id}",
        json={"text": "Built Python APIs, SQL automation, and dashboards."},
    ).status_code == 200
    reconfirmed = client.patch(
        f"/api/profile-facts/{fact_id}", json={"verified": True}
    )
    assert reconfirmed.status_code == 200
    assert reconfirmed.json()["confirmed"] is True
    invalidated = client.get(export_path)
    assert invalidated.status_code == 409
    assert "changed" in invalidated.json()["detail"]
    assert client.get(
        f"/artifacts/{pending_artifact['artifact_id']}.pdf"
    ).status_code == 409
    approvals = client.get(f"/runs/{run_id}/approvals").json()
    assert [item["kind"] for item in approvals] == [
        "profile_confirmation",
        "shortlist_selection",
        "application_approval",
    ]


def test_rejected_live_shortlist_does_not_mark_job_shortlisted(
    client: TestClient,
) -> None:
    profile = _confirmed_profile(client)
    job = client.post(
        "/jobs/manual",
        json={
            "title": "Python Engineer",
            "company": "Gate Rejection Example",
            "description": "Build Python APIs and SQL automation.",
            "location": "Remote",
            "remote": True,
            "url": "https://jobs.example.test/gate-rejection",
            "posted_at": "2026-08-20T00:00:00Z",
        },
    ).json()
    run_id = client.post(
        "/api/search-runs",
        json={
            "mode": "live",
            "profile_id": profile["profile_id"],
            "search": {"query": "Python", "sources": ["manual"]},
        },
    ).json()["run_id"]

    _approve(client, _pending(client, run_id, "profile_confirmation"))
    shortlist = _pending(client, run_id, "shortlist_selection")
    response = client.post(
        f"/api/approvals/{shortlist['approval_id']}/decisions",
        json={"decision": "skip", "entity_ids": []},
    )
    assert response.status_code == 200, response.text
    assert wait_for_run(client, run_id)["status"] == "cancelled"
    assert client.get(
        f"/api/jobs/{job['job_id']}/pipeline-status"
    ).json()["status"] == "eligible"


def test_live_requires_a_confirmed_profile(client: TestClient) -> None:
    profile = client.post("/profiles", json={"name": "Unconfirmed"}).json()
    response = client.post(
        "/api/search-runs",
        json={"mode": "live", "profile_id": profile["profile_id"]},
    )
    assert response.status_code == 422


def test_live_rejects_auto_approval(client: TestClient) -> None:
    profile = _confirmed_profile(client)
    response = client.post(
        "/api/search-runs",
        json={
            "mode": "live",
            "profile_id": profile["profile_id"],
            "auto_approve": True,
        },
    )
    assert response.status_code == 422


def test_cancelling_a_live_gate_is_terminal(client: TestClient) -> None:
    profile = _confirmed_profile(client)
    run_id = client.post(
        "/api/search-runs",
        json={"mode": "live", "profile_id": profile["profile_id"]},
    ).json()["run_id"]
    _pending(client, run_id, "profile_confirmation")
    cancelled = client.post(f"/api/runs/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    time.sleep(0.15)
    assert client.get(f"/runs/{run_id}").json()["status"] == "cancelled"


def test_live_pending_gate_recovers_after_process_restart(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "restart.sqlite3",
        replay_delay_ms=0,
        session_token="restart-test-token",
    )
    with TestClient(create_app(settings=settings)) as first:
        first.get("/api/session").raise_for_status()
        profile = _confirmed_profile(first)
        first.post(
            "/jobs/manual",
            json={
                "title": "Python Engineer",
                "company": "Restart Example",
                "description": "Python APIs and SQL automation",
                "remote": True,
                "url": "https://jobs.example.test/restart",
                "posted_at": "2026-08-20T00:00:00Z",
            },
        ).raise_for_status()
        response = first.post(
            "/api/search-runs",
            json={
                "mode": "live",
                "profile_id": profile["profile_id"],
                "search": {"query": "Python", "sources": ["manual"]},
            },
        )
        response.raise_for_status()
        run_id = response.json()["run_id"]
        original = _pending(first, run_id, "profile_confirmation")
        original_requests = [
            event
            for event in first.get(f"/runs/{run_id}/events").json()
            if event["type"] == "approval_requested"
        ]
        assert len(original_requests) == 1

    with TestClient(create_app(settings=settings)) as second:
        second.get("/api/session").raise_for_status()
        pending = _pending(second, run_id, "profile_confirmation")
        assert pending["approval_id"] == original["approval_id"]
        assert len(second.get(f"/runs/{run_id}/approvals").json()) == 1
        _approve(second, pending)
        next_gate = _pending(second, run_id, "shortlist_selection")
        assert next_gate["approval_id"] != original["approval_id"]
        requests_after_restart = [
            event
            for event in second.get(f"/runs/{run_id}/events").json()
            if event["type"] == "approval_requested"
        ]
        assert len(requests_after_restart) == 2

    with TestClient(create_app(settings=settings)) as third:
        third.get("/api/session").raise_for_status()
        recovered_shortlist = _pending(third, run_id, "shortlist_selection")
        assert recovered_shortlist["approval_id"] == next_gate["approval_id"]
        _approve(third, recovered_shortlist)
        application_gate = _pending(third, run_id, "application_approval")

    with TestClient(create_app(settings=settings)) as fourth:
        fourth.get("/api/session").raise_for_status()
        recovered_application = _pending(fourth, run_id, "application_approval")
        assert recovered_application["approval_id"] == application_gate["approval_id"]
        _approve(fourth, recovered_application)
        completed = wait_for_run(fourth, run_id)
        assert completed["status"] == "completed"
        assert len(fourth.get(f"/runs/{run_id}/approvals").json()) == 3
        request_events = [
            event
            for event in fourth.get(f"/runs/{run_id}/events").json()
            if event["type"] == "approval_requested"
        ]
        assert len(request_events) == 3


def test_public_failure_event_does_not_expose_exception_details(
    client: TestClient,
) -> None:
    secret = r"TOPSECRET C:\private\resume.pdf prompt=steal-data"

    async def failing_connector(_request):
        raise RuntimeError(secret)

    client.app.state.connector_search = failing_connector
    profile = _confirmed_profile(client)
    response = client.post(
        "/api/search-runs",
        json={
            "mode": "live",
            "profile_id": profile["profile_id"],
            "search": {
                "sources": ["greenhouse"],
                "source_identifiers": {"greenhouse": "example"},
            },
        },
    )
    response.raise_for_status()
    run_id = response.json()["run_id"]
    _approve(client, _pending(client, run_id, "profile_confirmation"))
    failed = wait_for_run(client, run_id)
    assert failed["status"] == "failed"
    assert failed["error"] == "The local run failed; inspect local logs"
    events = client.get(f"/runs/{run_id}/events").json()
    failure = [event for event in events if event["type"] == "run_failed"][-1]
    assert failure["payload"] == {
        "error_code": "run_failed",
        "message": "The local run failed; inspect local logs",
    }
    public_text = str(events)
    assert "TOPSECRET" not in public_text
    assert "resume.pdf" not in public_text
    assert "steal-data" not in public_text


def test_public_run_dto_removes_raw_agent_summaries_and_prompts(
    client: TestClient,
) -> None:
    stored = client.app.state.store.save_run(
        Run(
            status=RunStatus.COMPLETED,
            result={
                "ranked_jobs": [
                    {
                        "score": 91,
                        "job": {
                            "job_id": "job_safe",
                            "title": "Engineer",
                            "raw": {"secret": "provider-payload"},
                        },
                    }
                ],
                "agent_summaries": {"reviewer": "private model output"},
                "debug_prompt": "private system prompt",
            },
        )
    )
    response = client.get(f"/api/search-runs/{stored.run_id}")
    response.raise_for_status()
    result = response.json()["result"]
    assert result["ranked_jobs"][0]["job"] == {
        "job_id": "job_safe",
        "title": "Engineer",
    }
    assert "agent_summaries" not in result
    assert "debug_prompt" not in result
    listed = client.get("/api/search-runs").json()
    listed_result = next(item for item in listed if item["run_id"] == stored.run_id)[
        "result"
    ]
    assert "provider-payload" not in str(listed_result)
    assert "private model output" not in str(listed_result)
