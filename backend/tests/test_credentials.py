from __future__ import annotations

import pytest

from job_orchestrator.credentials import CredentialStore, CredentialStoreUnavailable


def test_credentials_refuse_non_windows_plaintext_fallback(monkeypatch) -> None:
    monkeypatch.setattr("job_orchestrator.credentials.platform.system", lambda: "Linux")
    store = CredentialStore("service", "account")

    with pytest.raises(CredentialStoreUnavailable, match="Windows Credential Manager"):
        store.set("sk-secret")
