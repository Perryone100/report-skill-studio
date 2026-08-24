"""Public contracts for declarative report Skills."""

from .loader import SkillLoadError, load_skill
from .models import (
    AppliedCorrection,
    ForbiddenPhraseRule,
    LoadedSkill,
    NormalizationResult,
    RequiredSectionRule,
    SkillFiles,
    SkillManifest,
    SkillTemplates,
    TermEntry,
    Terminology,
    TerminologyLayer,
    TerminologyValidationRule,
    ValidationIssue,
    ValidationResult,
    ValidationRules,
    ValidationSeverity,
)
from .normalization import normalize_transcript
from .validation import validate_report

__all__ = [
    "AppliedCorrection",
    "ForbiddenPhraseRule",
    "LoadedSkill",
    "NormalizationResult",
    "RequiredSectionRule",
    "SkillFiles",
    "SkillLoadError",
    "SkillManifest",
    "SkillTemplates",
    "TermEntry",
    "Terminology",
    "TerminologyLayer",
    "TerminologyValidationRule",
    "ValidationIssue",
    "ValidationResult",
    "ValidationRules",
    "ValidationSeverity",
    "load_skill",
    "normalize_transcript",
    "validate_report",
]
