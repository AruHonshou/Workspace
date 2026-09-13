from typing import Any, Self

import httpx
import pytest
from job_orchestrator.config import Settings
from job_orchestrator.providers.ai.deepseek import DeepSeekError, DeepSeekProvider
from pydantic import BaseModel, ConfigDict


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str


class Credential:
    def __init__(self, value: str | None):
        self.value = value

    def get(self) -> str | None:
        return self.value


class FakeResponse:
    def __init__(self, status: int, body: dict[str, Any]):
        self.status_code = status
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


class FakeClient:
    response = FakeResponse(
        200, {"choices": [{"message": {"content": '{"message":"ok"}'}}]}
    )
    last_request: dict[str, Any] | None = None

    def __init__(self, **_kwargs: Any):
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.__class__.last_request = {"url": url, **kwargs}
        return self.__class__.response


def test_direct_deepseek_completion_is_typed_and_uses_official_chat_endpoint(
    monkeypatch,
) -> None:
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = DeepSeekProvider(Settings(), Credential("secret-key"))  # type: ignore[arg-type]
    result = provider.structured_completion(
        system_prompt="Return a result.", data={"role": "QA"}, output_model=Output
    )
    assert result.message == "ok"
    assert FakeClient.last_request is not None
    assert FakeClient.last_request["url"] == "https://api.deepseek.com/chat/completions"
    assert FakeClient.last_request["headers"]["Authorization"] == "Bearer secret-key"
    assert FakeClient.last_request["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "API key"), (402, "saldo"), (429, "límite")],
)
def test_direct_deepseek_errors_are_clear_and_do_not_expose_secrets(
    monkeypatch, status: int, message: str
) -> None:
    FakeClient.response = FakeResponse(
        status, {"error": {"message": "secret-key internal"}}
    )
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = DeepSeekProvider(Settings(), Credential("secret-key"))  # type: ignore[arg-type]
    with pytest.raises(DeepSeekError, match=message) as captured:
        provider.structured_completion(
            system_prompt="Return a result.", data={"role": "QA"}, output_model=Output
        )
    assert "secret-key" not in str(captured.value)


def test_direct_deepseek_retries_one_incomplete_transport_response(monkeypatch) -> None:
    class FlakyClient(FakeClient):
        calls = 0

        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            self.__class__.calls += 1
            if self.__class__.calls == 1:
                raise httpx.RemoteProtocolError("incomplete chunked read")
            return FakeResponse(
                200,
                {"choices": [{"message": {"content": '{"message":"ok"}'}}]},
            )

    monkeypatch.setattr(httpx, "Client", FlakyClient)
    monkeypatch.setattr(
        "job_orchestrator.providers.ai.deepseek.sleep", lambda _seconds: None
    )
    provider = DeepSeekProvider(Settings(), Credential("secret-key"))  # type: ignore[arg-type]

    result = provider.structured_completion(
        system_prompt="Return a result.", data={}, output_model=Output
    )

    assert result.message == "ok"
    assert FlakyClient.calls == 2
