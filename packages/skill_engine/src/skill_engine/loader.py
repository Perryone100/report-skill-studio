"""Secure loading for a directory-backed declarative Skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, ValidationError

from .models import LoadedSkill, SkillManifest, Terminology, ValidationRules


class SkillLoadError(ValueError):
    """Raised when a Skill is missing, invalid, or references unsafe files."""


ModelT = TypeVar("ModelT", bound=BaseModel)


def _mapping_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SkillLoadError(f"Unable to read YAML file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillLoadError(f"YAML file must contain a mapping: {path}")
    return data


def _typed_yaml(path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate(_mapping_yaml(path))
    except ValidationError as exc:
        raise SkillLoadError(f"Invalid {path.name}: {exc}") from exc


def _resolve_file(root: Path, relative_path: str) -> Path:
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise SkillLoadError(f"Skill file escapes its directory: {relative_path}")
    if not candidate.is_file():
        raise SkillLoadError(f"Skill file does not exist: {relative_path}")
    return candidate


def _read_text(root: Path, relative_path: str) -> str:
    path = _resolve_file(root, relative_path)
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SkillLoadError(f"Unable to read Skill file {relative_path}: {exc}") from exc


def _read_schema(root: Path, relative_path: str) -> dict[str, Any]:
    path = _resolve_file(root, relative_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillLoadError(f"Unable to read JSON Schema {relative_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillLoadError(f"JSON Schema must contain an object: {relative_path}")
    try:
        Draft202012Validator.check_schema(data)
    except SchemaError as exc:
        raise SkillLoadError(f"Invalid JSON Schema {relative_path}: {exc.message}") from exc
    return data


def load_skill(directory: str | Path) -> LoadedSkill:
    """Load and validate the declarative files in ``directory``.

    No file from a Skill is imported or executed. All references must resolve under
    the Skill root, including symlinks.
    """

    root = Path(directory).expanduser()
    if not root.is_dir():
        raise SkillLoadError(f"Skill directory does not exist: {root}")
    root = root.resolve()

    manifest_path = root / "skill.yaml"
    if not manifest_path.is_file():
        raise SkillLoadError(f"Skill manifest does not exist: {manifest_path}")
    manifest = _typed_yaml(manifest_path, SkillManifest)
    files = manifest.files

    return LoadedSkill(
        root=root,
        manifest=manifest,
        instructions=_read_text(root, files.instructions),
        prompt=_read_text(root, files.prompt),
        report_schema=_read_schema(root, files.report_schema),
        terminology=_typed_yaml(_resolve_file(root, files.terms), Terminology),
        validation_rules=_typed_yaml(
            _resolve_file(root, files.validation), ValidationRules
        ),
    )
