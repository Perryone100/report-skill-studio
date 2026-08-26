from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI

from .config import Settings, get_settings
from .local_library import LocalMarkdownLibrary
from .providers import MockChatProvider, OpenAICompatibleChatProvider
from .services import ProviderRegistry, ReportGenerationService, SkillRegistry
from .storage import SQLiteStore


@lru_cache
def get_store() -> SQLiteStore:
    return SQLiteStore(get_settings().database_path)


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    providers = [MockChatProvider()]
    for connection in settings.openai_compatible_connection_configs:
        providers.extend(
            OpenAICompatibleChatProvider(
                base_url=connection.base_url,
                api_key=connection.api_key.get_secret_value(),
                model=model,
                provider_id=f"openai-compatible:{connection.id}:{model}",
                provider_name=connection.name,
            )
            for model in connection.models
        )
    if (
        settings.openai_compatible_base_url
        and settings.openai_compatible_api_key
        and settings.openai_compatible_model_names
    ):
        providers.extend(
            OpenAICompatibleChatProvider(
                base_url=settings.openai_compatible_base_url,
                api_key=settings.openai_compatible_api_key.get_secret_value(),
                model=model,
                provider_id=f"openai-compatible:{model}",
            )
            for model in settings.openai_compatible_model_names
        )
    return ProviderRegistry(providers)


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    return build_provider_registry(get_settings())


@lru_cache
def get_skill_registry() -> SkillRegistry:
    settings = get_settings()
    return SkillRegistry(settings.skills_dir, settings.user_skills_dir)


def get_local_library(store: SQLiteStore = Depends(get_store)) -> LocalMarkdownLibrary:
    return LocalMarkdownLibrary(store, get_settings().projects_dir)


def get_generation_service(
    store: SQLiteStore = Depends(get_store),
    providers: ProviderRegistry = Depends(get_provider_registry),
    skills: SkillRegistry = Depends(get_skill_registry),
    local_library: LocalMarkdownLibrary = Depends(get_local_library),
) -> ReportGenerationService:
    return ReportGenerationService(
        store,
        providers,
        skills,
        get_settings().artifacts_dir,
        local_library,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings().ensure_directories()
    get_store().initialize()
    yield
