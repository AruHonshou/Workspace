from __future__ import annotations

import pytest

from job_orchestrator.credentials import CredentialStore, CredentialStoreUnavailable


def test_credentials_refuse_insecure_linux_plaintext_fallback(monkeypatch) -> None:
    monkeypatch.setattr("job_orchestrator.credentials.platform.system", lambda: "Linux")
    store = CredentialStore("service", "account")

    with pytest.raises(
        CredentialStoreUnavailable, match="secure Linux credential vault"
    ):
        store.set("sk-secret")


def test_credentials_read_runtime_secret_file_without_keyring(
    monkeypatch, tmp_path
) -> None:
    secret_file = tmp_path / "deepseek"
    secret_file.write_text("sk-mounted\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY_FILE", str(secret_file))
    store = CredentialStore(
        "service",
        "account",
        env_var="DEEPSEEK_API_KEY",
        secret_file_env_var="DEEPSEEK_API_KEY_FILE",
    )

    assert store.get() == "sk-mounted"
    with pytest.raises(CredentialStoreUnavailable, match="read-only"):
        store.set("replacement")
