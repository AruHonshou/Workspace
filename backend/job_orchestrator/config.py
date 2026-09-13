from __future__ import annotations

from pathlib import Path
from secrets import token_urlsafe

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOB_ORCHESTRATOR_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Field(default=Path(".local/job-orchestrator"))
    artifact_dir: Path | None = None
    database_path: Path | None = None
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_reasoning_effort: str = "high"
    deepseek_max_concurrency: int = Field(default=1, ge=1, le=4)
    # Persistent vault namespace: retain access to keys saved by existing installs.
    # This is a storage identifier, not a user-facing product name.
    credential_service: str = "Career Orchestrator"
    credential_account: str = "deepseek-api-key"
    theirstack_credential_account: str = "theirstack-api-key"
    theirstack_base_url: str = "https://api.theirstack.com"
    theirstack_batch_size: int = Field(default=25, ge=1, le=25)
    request_timeout_seconds: float = Field(default=120.0, gt=0)
    session_token: str = Field(default_factory=lambda: token_urlsafe(32))
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )

    @field_validator("session_token", mode="before")
    @classmethod
    def generate_blank_session_token(cls, value: object) -> str:
        if value is None or not str(value).strip():
            return token_urlsafe(32)
        return str(value)

    @field_validator("host")
    @classmethod
    def bind_loopback_only(cls, value: str) -> str:
        if value.casefold() not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Workspace may only bind to a loopback address")
        return value

    @property
    def resolved_database_path(self) -> Path:
        return self.database_path or self.data_dir / "job_orchestrator.sqlite3"

    @property
    def artifacts_dir(self) -> Path:
        return self.artifact_dir or self.data_dir / "artifacts"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
