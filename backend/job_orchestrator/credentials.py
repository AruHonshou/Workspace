from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

import keyring
from keyring.errors import KeyringError


class CredentialStoreUnavailable(RuntimeError):
    """Raised when the operating-system credential vault cannot be used safely."""


@dataclass(frozen=True, slots=True)
class CredentialStore:
    service: str
    account: str
    env_var: str | None = None
    secret_file_env_var: str | None = None

    def _runtime_secret(self) -> str | None:
        """Read an injected runtime secret without ever persisting it locally."""

        if self.secret_file_env_var:
            configured_path = os.getenv(self.secret_file_env_var, "").strip()
            if configured_path:
                path = Path(configured_path).expanduser()
                try:
                    if not path.is_file():
                        raise CredentialStoreUnavailable(
                            f"The secret file configured by {self.secret_file_env_var} is unavailable"
                        )
                    value = path.read_text(encoding="utf-8").strip()
                except OSError as exc:
                    raise CredentialStoreUnavailable(
                        "Unable to read the mounted secret file"
                    ) from exc
                if not value:
                    raise CredentialStoreUnavailable("The mounted secret file is empty")
                return value
        if self.env_var:
            value = os.getenv(self.env_var, "").strip()
            if value:
                return value
        return None

    def _ensure_secure_vault(self) -> None:
        system = platform.system()
        accepted_backend_tokens = {
            "Windows": ("windows",),
            "Darwin": ("macos", "keychain"),
            "Linux": ("secretservice", "libsecret"),
        }
        expected = accepted_backend_tokens.get(system)
        if expected is None:
            raise CredentialStoreUnavailable(
                f"A secure operating-system credential vault is not supported on {system}"
            )
        backend = keyring.get_keyring()
        backend_name = f"{type(backend).__module__}.{type(backend).__name__}".casefold()
        if (
            not any(token in backend_name for token in expected)
            or getattr(backend, "priority", 0) <= 0
        ):
            raise CredentialStoreUnavailable(
                f"A secure {system} credential vault backend is not available"
            )

    def get(self) -> str | None:
        runtime_secret = self._runtime_secret()
        if runtime_secret:
            return runtime_secret
        self._ensure_secure_vault()
        try:
            value = keyring.get_password(self.service, self.account)
        except KeyringError as exc:
            raise CredentialStoreUnavailable(
                "Unable to read the credential vault"
            ) from exc
        return value.strip() if value and value.strip() else None

    def set(self, secret: str) -> None:
        if self._runtime_secret():
            raise CredentialStoreUnavailable(
                "This credential is supplied by the runtime and is read-only"
            )
        self._ensure_secure_vault()
        value = secret.strip()
        if not value:
            raise ValueError("The API key cannot be empty")
        try:
            keyring.set_password(self.service, self.account, value)
        except KeyringError as exc:
            raise CredentialStoreUnavailable(
                "Unable to write the credential vault"
            ) from exc

    def delete(self) -> bool:
        if self._runtime_secret():
            raise CredentialStoreUnavailable(
                "This credential is supplied by the runtime and is read-only"
            )
        self._ensure_secure_vault()
        try:
            if keyring.get_password(self.service, self.account) is None:
                return False
            keyring.delete_password(self.service, self.account)
        except KeyringError as exc:
            raise CredentialStoreUnavailable(
                "Unable to update the credential vault"
            ) from exc
        return True
