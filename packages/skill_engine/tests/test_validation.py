from __future__ import annotations

from copy import deepcopy
from dataclasses import replace


def _paragraph(report: dict[str, object], section_id: str) -> dict[str, object]:
    sections = report["sections"]
    assert isinstance(sections, list)
    section = next(item for item in sections if item["id"] == section_id)
    return section["blocks"][0]


def test_valid_reference_report_has_no_issues(default_skill, valid_report) -> None:
    result = default_skill.validate(valid_report)

    assert result.valid
    assert result.issues == []
    assert result.model_dump() == {"issues": [], "valid": True}


def test_reports_demo_term_as_noncanonical(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    _paragraph(report, "overall_conclusion")["text"] = "事项已登记到任务看版。"

    result = default_skill.validate(report)
    issues = [issue for issue in result.issues if issue.code == "terminology.noncanonical"]

    assert not result.valid
    assert len(issues) == 1
    assert issues[0].value == "任务看版"
    assert issues[0].suggestion == "任务看板"
    assert issues[0].path.endswith(".text")


def test_reports_longest_synthetic_variant(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    _paragraph(report, "overall_conclusion")["text"] = "星云计划项目下周继续宣讲。"

    result = default_skill.validate(report)
    issues = [issue for issue in result.issues if issue.rule_id == "term:星云项目"]

    assert len(issues) == 1
    assert issues[0].value == "星云计划项目"
    assert issues[0].suggestion == "星云项目"


def test_forbids_internal_graphic_edition_label(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    report["title"] = "产品研发周会纪要｜图文结合版"

    result = default_skill.validate(report)
    issues = [issue for issue in result.issues if issue.code == "phrase.forbidden"]

    assert len(issues) == 1
    assert issues[0].value == "图文结合版"
    assert issues[0].path == "$.title"
    assert issues[0].severity == "warning"
    assert result.valid


def test_allows_ai_generation_as_business_content(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    report["executive_summary"] = "本周完成 AI 生成报告能力联调。"

    result = default_skill.validate(report)

    assert result.valid
    assert all(issue.code != "phrase.forbidden" for issue in result.issues)


def test_missing_required_section_returns_structured_issue(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    report["sections"] = [
        section
        for section in report["sections"]
        if section["id"] != "risks_and_coordination"
    ]

    result = default_skill.validate(report)
    issue = next(
        item for item in result.issues if item.rule_id == "risks_and_coordination"
    )

    assert issue.code == "section.missing"
    assert issue.severity == "error"
    assert issue.path == "$.sections"
    assert issue.suggestion is not None


def test_schema_errors_are_returned_as_issues(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    report["meeting_date"] = "2026/08/21"

    result = default_skill.validate(report)

    issue = next(item for item in result.issues if item.code == "schema.invalid")
    assert issue.path == "$.meeting_date"
    assert not result.valid


def test_unconfirmed_correction_is_not_enforced(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    _paragraph(report, "overall_conclusion")["text"] = "事项已登记到任务看版。"
    terms = [
        term.model_copy(update={"confirmed": False})
        if term.canonical == "任务看板"
        else term
        for term in default_skill.terminology.terms
    ]
    skill = replace(
        default_skill,
        terminology=default_skill.terminology.model_copy(update={"terms": terms}),
    )

    result = skill.validate(report)

    assert all(issue.rule_id != "term:任务看板" for issue in result.issues)


def test_rejects_project_name_as_section_title(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    report["sections"][1]["title"] = "星云项目"

    result = default_skill.validate(report)

    issue = next(item for item in result.issues if item.code == "section.title_mismatch")
    assert issue.path == "$.sections[1].title"
    assert issue.suggestion == "本周工作进展"
    assert not result.valid


def test_rejects_extra_project_section(default_skill, valid_report) -> None:
    report = deepcopy(valid_report)
    report["sections"].append(
        {
            "id": "synthetic_project",
            "title": "星云项目",
            "blocks": [{"type": "paragraph", "text": "不应成为独立章节。"}],
        }
    )

    result = default_skill.validate(report)

    issue = next(item for item in result.issues if item.code == "section.unexpected")
    assert issue.path == "$.sections[4]"
    assert not result.valid
