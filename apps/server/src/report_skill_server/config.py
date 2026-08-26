from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: str = "http://localhost:4173,http://127.0.0.1:4173"

    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: SecretStr | None = None
    openai_compatible_model: str | None = None
    openai_compatible_models: str | None = None

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

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.user_skills_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
