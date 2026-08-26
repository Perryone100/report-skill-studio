from __future__ import annotations

import json
import ipaddress
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_provider_base_url(value: str) -> str:
    """Require HTTPS except for an explicitly loopback HTTP endpoint."""

    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base_url must be a valid http:// or https:// URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url cannot contain credentials, a query, or a fragment")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("base_url contains an invalid port") from exc
    if parsed.scheme == "http":
        hostname = parsed.hostname.lower()
        is_loopback = hostname == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if not is_loopback:
            raise ValueError("remote model endpoints must use HTTPS; HTTP is loopback-only")
    return normalized


class OpenAICompatibleConnectionConfig(BaseModel):
    """One independently authenticated OpenAI-compatible model endpoint."""

    id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=2000)
    api_key: SecretStr
    models: list[str] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("connection id must be lowercase kebab-case")
        return normalized

    @field_validator("name", "base_url")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return validate_provider_base_url(value)

    @field_validator("models")
    @classmethod
    def normalize_models(cls, values: list[str]) -> list[str]:
        models: list[str] = []
        seen: set[str] = set()
        for value in values:
            model = value.strip()
            if not model or model in seen:
                continue
            seen.add(model)
            models.append(model)
        if not models:
            raise ValueError("models must contain at least one model id")
        return models

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("api_key cannot be blank")
        return value


class Settings(BaseSettings):
    """Runtime settings. Secrets are read from the environment only."""

    model_config = SettingsConfigDict(
        env_prefix="RSS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Report Skill Studio"
    data_dir: Path = Field(default=Path("data"))
    skills_dir: Path = Field(default=Path("skills"))
    projects_dir: Path = Field(
        default_factory=lambda: Path.home() / "Documents" / "Report Skill Studio"
    )
    cors_origins: str = "http://localhost:4173,http://127.0.0.1:4173"
    allowed_hosts: str = "127.0.0.1,localhost,::1,testserver"

    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: SecretStr | None = None
    openai_compatible_model: str | None = None
    openai_compatible_models: str | None = None
    openai_compatible_connections: str | None = None

    @model_validator(mode="after")
    def validate_enabled_legacy_connection(self) -> "Settings":
        if (
            self.openai_compatible_base_url
            and self.openai_compatible_api_key
            and self.openai_compatible_model_names
        ):
            self.openai_compatible_base_url = validate_provider_base_url(
                self.openai_compatible_base_url
            )
        return self

    @property
    def openai_compatible_model_names(self) -> list[str]:
        """Return de-duplicated model ids while preserving configured order.

        ``RSS_OPENAI_COMPATIBLE_MODELS`` is the multi-model setting.  The
        singular setting remains supported so existing local ``.env`` files
        keep working unchanged.
        """

        raw_models = self.openai_compatible_models or self.openai_compatible_model or ""
        model_names: list[str] = []
        seen: set[str] = set()
        for candidate in raw_models.replace("\n", ",").split(","):
            model_name = candidate.strip()
            if not model_name or model_name in seen:
                continue
            seen.add(model_name)
            model_names.append(model_name)
        return model_names

    @property
    def openai_compatible_connection_configs(
        self,
    ) -> list[OpenAICompatibleConnectionConfig]:
        """Parse independently authenticated connections from a JSON array."""

        raw = (self.openai_compatible_connections or "").strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("RSS_OPENAI_COMPATIBLE_CONNECTIONS must be valid JSON") from exc
        if not isinstance(payload, list):
            raise ValueError("RSS_OPENAI_COMPATIBLE_CONNECTIONS must be a JSON array")

        connections = [OpenAICompatibleConnectionConfig.model_validate(item) for item in payload]
        ids = [connection.id for connection in connections]
        if len(ids) != len(set(ids)):
            raise ValueError("connection ids in RSS_OPENAI_COMPATIBLE_CONNECTIONS must be unique")
        return connections

    @property
    def database_path(self) -> Path:
        return self.data_dir / "report-skill-studio.sqlite3"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def user_skills_dir(self) -> Path:
        """Writable Skill catalog kept with local runtime data, outside Git."""

        return self.data_dir / "skills"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_origins(self) -> list[str]:
        return list(dict.fromkeys([
            *self.allowed_origins,
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ]))

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.user_skills_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
