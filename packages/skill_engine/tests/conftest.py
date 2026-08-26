from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_engine import LoadedSkill, load_skill


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SKILL_ROOT = REPOSITORY_ROOT / "skills" / "default-weekly-meeting"


@pytest.fixture(scope="session")
def default_skill() -> LoadedSkill:
    return load_skill(DEFAULT_SKILL_ROOT)


@pytest.fixture(scope="session")
def default_skill_directory() -> Path:
    return DEFAULT_SKILL_ROOT


@pytest.fixture()
def valid_report() -> dict[str, object]:
    path = DEFAULT_SKILL_ROOT / "examples" / "expected.json"
    return json.loads(path.read_text(encoding="utf-8"))
