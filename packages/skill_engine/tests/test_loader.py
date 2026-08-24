from __future__ import annotations

from pathlib import Path

import pytest

from skill_engine import SkillLoadError, load_skill


def test_loads_bundled_default_skill(default_skill) -> None:
    assert default_skill.manifest.id == "default-weekly-meeting"
    assert default_skill.manifest.version == "0.2.0"
    assert default_skill.instructions.startswith("# 通用周会纪要写作规则")
    assert "{{transcript}}" in default_skill.prompt
    assert default_skill.report_schema["$schema"].endswith("2020-12/schema")
    assert {term.canonical for term in default_skill.terminology.terms} == {
        "任务看板",
        "星云项目",
        "OCR",
    }


def test_invalid_manifest_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "skill.yaml").write_text(
        """
schema_version: "0.1"
id: Invalid Skill Id
name: 测试
version: latest
description: 无效清单
unexpected: true
files: {}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SkillLoadError, match="Invalid skill.yaml"):
        load_skill(tmp_path)


def test_manifest_cannot_escape_skill_directory(tmp_path: Path) -> None:
    (tmp_path / "skill.yaml").write_text(
        """
schema_version: "0.1"
id: unsafe-skill
name: Unsafe
version: 0.1.0
description: Unsafe path fixture
files:
  instructions: ../instructions.md
  prompt: prompt.md
  report_schema: schema.json
  terms: terms.yaml
  validation: rules.yaml
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SkillLoadError, match="safe relative file path"):
        load_skill(tmp_path)
