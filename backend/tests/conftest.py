from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from job_orchestrator.ai_contracts import (
    AIInvocationResult,
    AIOperation,
    ContentProposal,
    FitAnalystProposal,
)
from job_orchestrator.api import create_app
from job_orchestrator.config import Settings


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


class FakeAIClient:
    def invoke(self, operation, payload):
        structured = {
            AIOperation.FIT_ANALYSIS: FitAnalystProposal(
                mappings=[], executive_summary="Evidence-first fixture analysis."
            ),
            AIOperation.CONTENT_WRITING: ContentProposal(selections=[]),
        }[operation]
        return AIInvocationResult(
            content=structured.model_dump_json(), model="fixture", structured=structured
        )


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "test.sqlite3",
    )
    with TestClient(create_app(settings=settings)) as value:
        value.app.state.credential_store = FakeCredentialStore()
        # Tests must never discover or spend a real TheirStack credential from
        # Windows Credential Manager. Connector behavior is injected per test.
        value.app.state.theirstack_credential_store = FakeCredentialStore(None)
        value.app.state.theirstack_client = None
        value.app.state.ai_client = FakeAIClient()
        value.get("/api/session").raise_for_status()
        yield value
