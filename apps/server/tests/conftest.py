from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from report_skill_server.main import (
    create_app,
    get_local_library,
    get_provider_registry,
    get_skill_registry,
    get_store,
)
from report_skill_server.local_library import LocalMarkdownLibrary
from report_skill_server.providers import MockChatProvider
from report_skill_server.services import ProviderRegistry, SkillRegistry
from report_skill_server.storage import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "test.sqlite3")


@pytest.fixture
def client(store: SQLiteStore, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry([MockChatProvider()])
    skills_dir = Path(__file__).resolve().parents[3] / "skills"
    app.dependency_overrides[get_skill_registry] = lambda: SkillRegistry(
        skills_dir,
        tmp_path / "user-skills",
    )
    app.dependency_overrides[get_local_library] = lambda: LocalMarkdownLibrary(
        store,
        tmp_path / "markdown-library",
    )
    with TestClient(app) as test_client:
        yield test_client
