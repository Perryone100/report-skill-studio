from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Run the public API against isolated local-only dependencies."""

    repository_root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("RSS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RSS_SKILLS_DIR", str(repository_root / "skills"))

    from report_skill_server.config import get_settings
    from report_skill_server.main import (
        create_app,
        get_provider_registry,
        get_skill_registry,
        get_store,
    )
    from report_skill_server.providers import MockChatProvider
    from report_skill_server.services import ProviderRegistry, SkillRegistry
    from report_skill_server.storage import SQLiteStore

    get_settings.cache_clear()
    get_store.cache_clear()
    store = SQLiteStore(tmp_path / "e2e.sqlite3")
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry(
        [MockChatProvider()]
    )
    app.dependency_overrides[get_skill_registry] = lambda: SkillRegistry(
        repository_root / "skills"
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_store.cache_clear()
    get_settings.cache_clear()
