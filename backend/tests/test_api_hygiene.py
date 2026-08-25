from __future__ import annotations

import asyncio
import hashlib
import time
from typing import ClassVar

import httpx
import job_orchestrator.api as api_module
from conftest import wait_for_run
from fastapi.testclient import TestClient


class FakeDeepSeekClient:
    calls: ClassVar[list[tuple[dict, dict]]] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str, *, headers: dict):
        self.calls.append((headers, {}))
        return httpx.Response(
            200,
            json={"data": [{"id": "deepseek-v4-pro", "object": "model"}]},
            request=httpx.Request("GET", f"https://api.deepseek.com{url}"),
        )


def test_profile_import_offloads_extraction_and_uses_stable_document_id(
    client: TestClient, monkeypatch
) -> None:
    original_to_thread = asyncio.to_thread
    calls: list[tuple[object, tuple[object, ...]]] = []

    async def tracked_to_thread(function, /, *args, **kwargs):
        calls.append((function, args))
        return await original_to_thread(function, *args, **kwargs)

    monkeypatch.setattr(api_module.asyncio, "to_thread", tracked_to_thread)
    content = b"Python and SQL skills for production APIs.\nBuilt reliable data services."
    response = client.post(
        "/api/profiles/import",
        files={"file": ("resume.txt", content, "text/plain")},
    )

    assert response.status_code == 201, response.text
    assert calls and calls[0][0] is api_module.extract_document_text
    expected_id = f"document_{hashlib.sha256(content).hexdigest()}"
    facts = response.json()["profile"]["facts"]
    assert facts
    assert {fact["source_document_id"] for fact in facts} == {expected_id}


def test_artifact_alias_and_delete_reset_all_local_state(client: TestClient) -> None:
    run_id = client.post(
        "/api/search-runs",
        json={"mode": "replay", "auto_approve": True},
    ).json()["run_id"]
    wait_for_run(client, run_id)
    artifact = client.get(f"/runs/{run_id}/artifacts").json()[0]
    artifact_id = artifact["artifact_id"]

    alias = client.get(f"/api/artifacts/{artifact_id}")
    assert alias.status_code == 200
    assert alias.json() == artifact
    prepared = client.post(f"/api/application-packs/{artifact_id}/export")
    assert prepared.status_code == 200, prepared.text
    downloaded = client.get(prepared.json()["download_url"])
    assert downloaded.status_code == 200
    assert any(client.app.state.settings.artifacts_dir.rglob("*"))

    previous_checkpointer = client.app.state.checkpointer
    deleted = client.request(
        "DELETE",
        "/api/data",
        json={"confirmation": "DELETE_ALL_LOCAL_DATA"},
    )

    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"
    assert client.app.state.checkpointer is not previous_checkpointer
    snapshot = client.get("/api/data/export").json()
    assert snapshot == {
        "profiles": [],
        "jobs": [],
        "runs": [],
        "events": [],
        "approvals": [],
        "artifacts": [],
    }
    assert list(client.app.state.settings.artifacts_dir.rglob("*")) == []
    assert client.get(f"/api/artifacts/{artifact_id}").status_code == 404
    checkpoint = client.app.state.checkpointer.get_tuple(
        {"configurable": {"thread_id": run_id}}
    )
    assert checkpoint is None


def test_delete_refuses_active_runs_and_requires_typed_confirmation(
    client: TestClient,
) -> None:
    invalid = client.request(
        "DELETE", "/api/data", json={"confirmation": "yes"}
    )
    assert invalid.status_code == 422

    run_id = client.post(
        "/api/search-runs",
        json={"mode": "replay", "auto_approve": False},
    ).json()["run_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if client.get(f"/runs/{run_id}").json()["status"] == "awaiting_user":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("Run did not reach an active approval gate")

    refused = client.request(
        "DELETE",
        "/api/data",
        json={"confirmation": "DELETE_ALL_LOCAL_DATA"},
    )
    assert refused.status_code == 409
    assert client.get(f"/runs/{run_id}").status_code == 200
    client.post(f"/api/runs/{run_id}/cancel").raise_for_status()


def test_deepseek_key_is_validated_but_never_returned_or_persisted(
    client: TestClient, monkeypatch
) -> None:
    secret = "synthetic-secret-value-for-test-only"
    client.app.state.credential_store.delete()
    FakeDeepSeekClient.calls.clear()
    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeDeepSeekClient)

    response = client.put("/api/settings/deepseek", json={"api_key": secret})

    assert response.status_code == 200, response.text
    assert response.json()["configured"] is True
    assert response.json()["model"] == "deepseek-v4-pro"
    assert secret not in response.text
    assert client.app.state.credential_store.get() == secret
    assert FakeDeepSeekClient.calls[0][0]["Authorization"] == f"Bearer {secret}"
    database = client.app.state.settings.resolved_database_path.read_bytes()
    assert secret.encode() not in database
    exported = client.get("/api/data/export")
    assert secret not in exported.text

    deleted = client.delete("/api/settings/deepseek")
    assert deleted.status_code == 200
    assert deleted.json()["configured"] is False
    assert secret not in deleted.text
