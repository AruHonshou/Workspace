from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import ClassVar

import httpx
from fastapi.testclient import TestClient

import job_orchestrator.api as api_module
from job_orchestrator.config import Settings


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


def test_owned_artifact_cleanup_is_confined_to_the_configured_root(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_directories()
    owned = settings.artifacts_dir / "ats" / "resume.pdf"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"generated")
    unrelated = tmp_path / "keep.pdf"
    unrelated.write_bytes(b"private")

    removed = api_module._remove_owned_artifact_files(
        settings, [str(owned), str(unrelated)]
    )

    assert removed == 1
    assert not owned.exists()
    assert unrelated.read_bytes() == b"private"


def test_profile_import_offloads_extraction_and_uses_stable_document_id(
    client: TestClient, monkeypatch
) -> None:
    original_to_thread = asyncio.to_thread
    calls: list[tuple[object, tuple[object, ...]]] = []

    async def tracked_to_thread(function, /, *args, **kwargs):
        calls.append((function, args))
        return await original_to_thread(function, *args, **kwargs)

    monkeypatch.setattr(api_module.asyncio, "to_thread", tracked_to_thread)
    content = (
        b"Python and SQL skills for production APIs.\nBuilt reliable data services."
    )
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


def test_delete_reset_all_local_state(client: TestClient) -> None:
    created = client.post(
        "/api/profiles", json={"display_name": "QA", "name": "Ada Local"}
    )
    assert created.status_code == 201
    deleted = client.request(
        "DELETE",
        "/api/data",
        json={"confirmation": "DELETE_ALL_LOCAL_DATA"},
    )

    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"
    assert not hasattr(client.app.state, "checkpointer")
    snapshot = client.get("/api/data/export").json()
    assert snapshot == {
        "profiles": [],
        "jobs": [],
        "searches": [],
    }
    assert list(client.app.state.settings.artifacts_dir.rglob("*")) == []
    assert client.get("/api/profiles").json() == []


def test_delete_requires_typed_confirmation(
    client: TestClient,
) -> None:
    invalid = client.request("DELETE", "/api/data", json={"confirmation": "yes"})
    assert invalid.status_code == 422

    accepted = client.request(
        "DELETE",
        "/api/data",
        json={"confirmation": "DELETE_ALL_LOCAL_DATA"},
    )
    assert accepted.status_code == 200


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
