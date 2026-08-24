"""Typed, non-executable contracts for a report Skill."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


_SKILL_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


class StrictModel(BaseModel):
    """Reject misspelled declarative fields instead of silently ignoring them."""

    model_config = ConfigDict(extra="forbid")


def _validate_relative_file(value: str) -> str:
    value = value.strip()
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value.endswith("/"):
        raise ValueError("must be a safe relative file path")
    return value


class SkillTemplates(StrictModel):
    """Trusted renderer assets selected by the Skill manifest."""

    html: str
    css: str

    _safe_html = field_validator("html")(_validate_relative_file)
    _safe_css = field_validator("css")(_validate_relative_file)


class SkillFiles(StrictModel):
    """Declarative files loaded from inside one Skill directory."""

    instructions: str
    prompt: str
    report_schema: str
    terms: str
    validation: str
    templates: SkillTemplates | None = None

    _safe_files = field_validator(
        "instructions", "prompt", "report_schema", "terms", "validation"
    )(_validate_relative_file)


class SkillManifest(StrictModel):
    """Metadata and local file references stored in ``skill.yaml``."""

    schema_version: str = Field(pattern=r"^0\.1$")
    id: str
    name: str = Field(min_length=1, max_length=120)
    version: str
    description: str = Field(min_length=1, max_length=500)
    locale: str = Field(default="zh-CN", min_length=2, max_length=35)
    files: SkillFiles

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not _SKILL_ID_PATTERN.fullmatch(value):
            raise ValueError("must be a lowercase kebab-case identifier")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _SEMVER_PATTERN.fullmatch(value):
            raise ValueError("must be a semantic version such as 0.1.0")
        return value


class TerminologyLayer(StrEnum):
    FIXED = "fixed"
    PROJECT = "project"
    TEMPORARY = "temporary"


class TermEntry(StrictModel):
    """One canonical term and the transcription variants that must replace it."""

    canonical: str = Field(min_length=1, max_length=120)
    variants: list[str] = Field(min_length=1)
    layer: TerminologyLayer = TerminologyLayer.FIXED
    confirmed: bool = False
    case_sensitive: bool = False
    note: str | None = Field(default=None, max_length=500)

    @field_validator("canonical")
    @classmethod
    def clean_canonical(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("variants")
    @classmethod
    def validate_variants(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("must not contain blank variants")
        normalized = [value.casefold() for value in cleaned]
        if len(normalized) != len(set(normalized)):
            raise ValueError("must not contain duplicate variants")
        return cleaned

    @model_validator(mode="after")
    def canonical_is_not_a_variant(self) -> "TermEntry":
        if self.canonical.casefold() in {value.casefold() for value in self.variants}:
            raise ValueError("canonical term must not also be listed as a variant")
        return self


class Terminology(StrictModel):
    schema_version: str = Field(pattern=r"^0\.1$")
    terms: list[TermEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def terms_are_unambiguous(self) -> "Terminology":
        owners: dict[str, str] = {}
        for term in self.terms:
            for token in [term.canonical, *term.variants]:
                normalized = token.casefold()
                existing = owners.get(normalized)
                if existing is not None and existing != term.canonical:
                    raise ValueError(
                        f"term {token!r} is ambiguous between {existing!r} and "
                        f"{term.canonical!r}"
                    )
                owners[normalized] = term.canonical
        return self


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RequiredSectionRule(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    severity: ValidationSeverity = ValidationSeverity.ERROR
    require_content: bool = True


class ForbiddenPhraseRule(StrictModel):
    phrase: str = Field(min_length=1, max_length=200)
    severity: ValidationSeverity = ValidationSeverity.ERROR
    case_sensitive: bool = False
    message: str | None = Field(default=None, max_length=500)


class TerminologyValidationRule(StrictModel):
    enabled: bool = True
    severity: ValidationSeverity = ValidationSeverity.ERROR
    confirmed_only: bool = True


class ValidationRules(StrictModel):
    schema_version: str = Field(pattern=r"^0\.1$")
    required_sections: list[RequiredSectionRule] = Field(default_factory=list)
    allow_additional_sections: bool = True
    forbidden_phrases: list[ForbiddenPhraseRule] = Field(default_factory=list)
    terminology: TerminologyValidationRule = Field(
        default_factory=TerminologyValidationRule
    )

    @model_validator(mode="after")
    def rules_are_unique(self) -> "ValidationRules":
        section_ids = [rule.id for rule in self.required_sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("required section ids must be unique")

        phrases = [rule.phrase.casefold() for rule in self.forbidden_phrases]
        if len(phrases) != len(set(phrases)):
            raise ValueError("forbidden phrases must be unique")
        return self


class ValidationIssue(StrictModel):
    """A stable, UI-friendly deterministic validation finding."""

    code: str
    severity: ValidationSeverity
    message: str
    path: str | None = None
    value: str | None = None
    suggestion: str | None = None
    rule_id: str | None = None


class ValidationResult(StrictModel):
    issues: list[ValidationIssue] = Field(default_factory=list)

    @computed_field
    @property
    def valid(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)


class AppliedCorrection(StrictModel):
    """A grouped replacement applied while normalizing source text."""

    original: str = Field(min_length=1)
    canonical: str = Field(min_length=1)
    count: int = Field(ge=1)


class NormalizationResult(StrictModel):
    """Normalized text and an ordered audit trail of actual replacements."""

    text: str
    corrections: list[AppliedCorrection] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LoadedSkill:
    """All model-facing and validator-facing data loaded from one directory."""

    root: Path
    manifest: SkillManifest
    instructions: str
    prompt: str
    report_schema: dict[str, Any]
    terminology: Terminology
    validation_rules: ValidationRules

    def validate(self, report: dict[str, Any]) -> ValidationResult:
        from .validation import validate_report

        return validate_report(report, self)

    def normalize_transcript(
        self, text: str, *, confirmed_only: bool = True
    ) -> NormalizationResult:
        from .normalization import normalize_transcript

        return normalize_transcript(
            text, self.terminology, confirmed_only=confirmed_only
        )
