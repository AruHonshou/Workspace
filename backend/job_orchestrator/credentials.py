from __future__ import annotations

import platform
from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError


class CredentialStoreUnavailable(RuntimeError):
    """Raised when the operating-system credential vault cannot be used safely."""


@dataclass(frozen=True, slots=True)
class CredentialStore:
    service: str
    account: str

    def _ensure_windows_vault(self) -> None:
        if platform.system() != "Windows":
            raise CredentialStoreUnavailable(
                "API credentials require Windows Credential Manager"
            )
        backend = keyring.get_keyring()
        backend_name = f"{type(backend).__module__}.{type(backend).__name__}".casefold()
        if "windows" not in backend_name or getattr(backend, "priority", 0) <= 0:
            raise CredentialStoreUnavailable(
                "A secure Windows Credential Manager backend is not available"
            )

    def get(self) -> str | None:
        self._ensure_windows_vault()
        try:
            value = keyring.get_password(self.service, self.account)
        except KeyringError as exc:
            raise CredentialStoreUnavailable("Unable to read Windows Credential Manager") from exc
        return value.strip() if value and value.strip() else None

    def set(self, secret: str) -> None:
        self._ensure_windows_vault()
        value = secret.strip()
        if not value:
            raise ValueError("The API key cannot be empty")
        try:
            keyring.set_password(self.service, self.account, value)
        except KeyringError as exc:
            raise CredentialStoreUnavailable("Unable to write Windows Credential Manager") from exc

    def delete(self) -> bool:
        self._ensure_windows_vault()
        try:
            if keyring.get_password(self.service, self.account) is None:
                return False
            keyring.delete_password(self.service, self.account)
        except KeyringError as exc:
            raise CredentialStoreUnavailable("Unable to update Windows Credential Manager") from exc
        return True
