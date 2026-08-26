"""Public contracts for declarative report Skills."""

from .compatibility import (
    CANONICAL_REPORT_FIELDS,
    SUPPORTED_BLOCK_TYPES,
    ensure_workbench_compatible,
    workbench_compatibility_issues,
)
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
    "CANONICAL_REPORT_FIELDS",
    "ForbiddenPhraseRule",
    "LoadedSkill",
    "NormalizationResult",
    "RequiredSectionRule",
    "SkillFiles",
    "SkillLoadError",
    "SkillManifest",
    "SkillTemplates",
    "SUPPORTED_BLOCK_TYPES",
    "TermEntry",
    "Terminology",
    "TerminologyLayer",
    "TerminologyValidationRule",
    "ValidationIssue",
    "ValidationResult",
    "ValidationRules",
    "ValidationSeverity",
    "ensure_workbench_compatible",
    "load_skill",
    "normalize_transcript",
    "validate_report",
    "workbench_compatibility_issues",
]
