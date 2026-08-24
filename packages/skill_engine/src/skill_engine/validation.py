"""Deterministic report validation independent of any model provider."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from jsonschema import Draft202012Validator

from .models import (
    LoadedSkill,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


def _json_path(parts: Sequence[str | int]) -> str:
    result = "$"
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            escaped = part.replace("~", "~0").replace("/", "~1")
            result += f".{escaped}"
    return result


def _walk_strings(value: Any, parts: tuple[str | int, ...] = ()) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield _json_path(parts), value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_strings(child, (*parts, str(key)))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from _walk_strings(child, (*parts, index))


def _contains(text: str, needle: str, *, case_sensitive: bool) -> bool:
    if case_sensitive:
        return needle in text
    return needle.casefold() in text.casefold()


def _section_has_content(section: Mapping[str, Any]) -> bool:
    if "blocks" in section:
        blocks = section["blocks"]
        return isinstance(blocks, list) and bool(blocks)
    for key, value in section.items():
        if key in {"id", "title"}:
            continue
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, dict)) and bool(value):
            return True
    return False


def _schema_issues(report: dict[str, Any], skill: LoadedSkill) -> list[ValidationIssue]:
    validator = Draft202012Validator(skill.report_schema)
    issues: list[ValidationIssue] = []
    for error in sorted(
        validator.iter_errors(report),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    ):
        issues.append(
            ValidationIssue(
                code="schema.invalid",
                severity=ValidationSeverity.ERROR,
                message=error.message,
                path=_json_path(tuple(error.absolute_path)),
                value=str(error.instance)[:200],
                rule_id="report_schema",
            )
        )
    return issues


def _required_section_issues(
    report: dict[str, Any], skill: LoadedSkill
) -> list[ValidationIssue]:
    raw_sections = report.get("sections", [])
    sections: dict[str, tuple[int, Mapping[str, Any]]] = {}
    section_entries: list[tuple[int, str, Mapping[str, Any]]] = []
    issues: list[ValidationIssue] = []
    if isinstance(raw_sections, list):
        for index, section in enumerate(raw_sections):
            if isinstance(section, Mapping) and isinstance(section.get("id"), str):
                section_id = section["id"]
                section_entries.append((index, section_id, section))
                if section_id in sections:
                    issues.append(
                        ValidationIssue(
                            code="section.duplicate_id",
                            severity=ValidationSeverity.ERROR,
                            message=f"章节 id 重复：{section_id}",
                            path=f"$.sections[{index}].id",
                            value=section_id,
                            suggestion="为每个章节使用唯一且符合 Skill 约定的 id",
                            rule_id=section_id,
                        )
                    )
                    continue
                sections[section_id] = (index, section)

    expected_sections = {
        rule.id: rule for rule in skill.validation_rules.required_sections
    }
    if not skill.validation_rules.allow_additional_sections:
        for index, section_id, _section in section_entries:
            if section_id not in expected_sections:
                issues.append(
                    ValidationIssue(
                        code="section.unexpected",
                        severity=ValidationSeverity.ERROR,
                        message=f"Skill 不允许额外章节：{section_id}",
                        path=f"$.sections[{index}]",
                        value=section_id,
                        suggestion="将该内容合并到 Skill 规定的章节内容块中",
                        rule_id=section_id,
                    )
                )

    for rule in skill.validation_rules.required_sections:
        found = sections.get(rule.id)
        if found is None:
            issues.append(
                ValidationIssue(
                    code="section.missing",
                    severity=rule.severity,
                    message=f"缺少必填章节：{rule.title}",
                    path="$.sections",
                    suggestion=f"添加 id 为 {rule.id!r} 的章节",
                    rule_id=rule.id,
                )
            )
            continue

        index, section = found
        if section.get("title") != rule.title:
            issues.append(
                ValidationIssue(
                    code="section.title_mismatch",
                    severity=rule.severity,
                    message=f"章节标题必须为：{rule.title}",
                    path=f"$.sections[{index}].title",
                    value=str(section.get("title", "")),
                    suggestion=rule.title,
                    rule_id=rule.id,
                )
            )
        if rule.require_content and not _section_has_content(section):
            issues.append(
                ValidationIssue(
                    code="section.empty",
                    severity=rule.severity,
                    message=f"必填章节没有内容：{rule.title}",
                    path=f"$.sections[{index}]",
                    suggestion="至少添加一个非空内容块",
                    rule_id=rule.id,
                )
            )
    return issues


def _forbidden_phrase_issues(
    strings: list[tuple[str, str]], skill: LoadedSkill
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for rule in skill.validation_rules.forbidden_phrases:
        for path, text in strings:
            if _contains(text, rule.phrase, case_sensitive=rule.case_sensitive):
                issues.append(
                    ValidationIssue(
                        code="phrase.forbidden",
                        severity=rule.severity,
                        message=rule.message or f"报告中不得出现：{rule.phrase}",
                        path=path,
                        value=rule.phrase,
                        suggestion=f"删除“{rule.phrase}”或改为对读者有意义的表述",
                        rule_id=rule.phrase,
                    )
                )
    return issues


def _terminology_issues(
    strings: list[tuple[str, str]], skill: LoadedSkill
) -> list[ValidationIssue]:
    setting = skill.validation_rules.terminology
    if not setting.enabled:
        return []

    issues: list[ValidationIssue] = []
    for term in skill.terminology.terms:
        if setting.confirmed_only and not term.confirmed:
            continue
        for path, text in strings:
            detected = [
                variant
                for variant in term.variants
                if _contains(text, variant, case_sensitive=term.case_sensitive)
            ]
            if detected:
                # Overlapping variants such as "星云计划" and "星云计划项目" describe one
                # correction. Report only the most specific match per field.
                variant = max(detected, key=len)
                issues.append(
                    ValidationIssue(
                        code="terminology.noncanonical",
                        severity=setting.severity,
                        message=f"术语“{variant}”应统一为“{term.canonical}”",
                        path=path,
                        value=variant,
                        suggestion=term.canonical,
                        rule_id=f"term:{term.canonical}",
                    )
                )
    return issues


def validate_report(report: dict[str, Any], skill: LoadedSkill) -> ValidationResult:
    """Validate schema, section contracts, forbidden phrases and terminology."""

    strings = list(_walk_strings(report))
    issues = [
        *_schema_issues(report, skill),
        *_required_section_issues(report, skill),
        *_forbidden_phrase_issues(strings, skill),
        *_terminology_issues(strings, skill),
    ]
    return ValidationResult(issues=issues)
