from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from job_orchestrator.agents import (
    AgentInvocationResult,
    CoordinatorProposal,
    FitAnalystProposal,
    ReviewerProposal,
    ScoutProposal,
    TailorProposal,
)
from job_orchestrator.api import create_app
from job_orchestrator.config import Settings
from job_orchestrator.schemas import AgentRole


class FakeCredentialStore:
    def __init__(self, value: str | None = "sk-test-key") -> None:
        self.value = value

    def get(self) -> str | None:
        return self.value

    def set(self, secret: str) -> None:
        self.value = secret

    def delete(self) -> bool:
        existed = self.value is not None
        self.value = None
        return existed


class FakeCareerAgentRegistry:
    def invoke(self, role, payload):
        aliases = payload.get("deterministic_aliases", []) if isinstance(payload, dict) else []
        structured = {
            AgentRole.COORDINATOR: CoordinatorProposal(summary="Fixture coordination"),
            AgentRole.SCOUT: ScoutProposal(summary="Fixture role expansion", aliases=aliases),
            AgentRole.FIT_ANALYST: FitAnalystProposal(mappings=[]),
            AgentRole.TAILOR: TailorProposal(selections=[]),
            AgentRole.REVIEWER: ReviewerProposal(observations=[]),
        }[role]
        return AgentInvocationResult(content=structured.model_dump_json(), model="fixture", structured=structured)


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(data_dir=tmp_path, database_path=tmp_path / "test.sqlite3", replay_delay_ms=0)
    with TestClient(create_app(settings=settings)) as value:
        value.app.state.credential_store = FakeCredentialStore()
        # Tests must never discover or spend a real TheirStack credential from
        # Windows Credential Manager. Connector behavior is injected per test.
        value.app.state.theirstack_credential_store = FakeCredentialStore(None)
        value.app.state.theirstack_client = None
        value.app.state.agent_registry = FakeCareerAgentRegistry()
        value.get("/api/session").raise_for_status()
        yield value


def wait_for_run(client: TestClient, run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/runs/{run_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"Run {run_id} did not finish")
