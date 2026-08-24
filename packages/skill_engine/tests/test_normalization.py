from __future__ import annotations

from skill_engine import TermEntry, Terminology, normalize_transcript


def test_normalizes_demo_term_and_groups_corrections(default_skill) -> None:
    result = default_skill.normalize_transcript("任务看版已登记，任务看版待复核。")

    assert result.text == "任务看板已登记，任务看板待复核。"
    assert result.model_dump() == {
        "text": "任务看板已登记，任务看板待复核。",
        "corrections": [
            {"original": "任务看版", "canonical": "任务看板", "count": 2}
        ],
    }


def test_longest_synthetic_project_variant_wins(default_skill) -> None:
    result = normalize_transcript(
        "星云计划项目完成宣讲，星云计划仍需跟进。",
        default_skill.terminology,
    )

    assert result.text == "星云项目完成宣讲，星云项目仍需跟进。"
    assert [correction.model_dump() for correction in result.corrections] == [
        {"original": "星云计划项目", "canonical": "星云项目", "count": 1},
        {"original": "星云计划", "canonical": "星云项目", "count": 1},
    ]


def test_unconfirmed_terms_are_ignored_by_default() -> None:
    terminology = Terminology(
        schema_version="0.1",
        terms=[
            TermEntry(
                canonical="标准项目",
                variants=["候选误词"],
                confirmed=False,
            )
        ],
    )

    default_result = normalize_transcript("候选误词", terminology)
    opted_in_result = normalize_transcript(
        "候选误词", terminology, confirmed_only=False
    )

    assert default_result.text == "候选误词"
    assert default_result.corrections == []
    assert opted_in_result.text == "标准项目"


def test_case_sensitive_term_preserves_other_case() -> None:
    terminology = Terminology(
        schema_version="0.1",
        terms=[
            TermEntry(
                canonical="OCR",
                variants=["O C R"],
                confirmed=True,
                case_sensitive=True,
            )
        ],
    )

    result = normalize_transcript("o c r / O C R", terminology)

    assert result.text == "o c r / OCR"
    assert result.corrections[0].original == "O C R"


def test_replacement_output_is_not_processed_again() -> None:
    terminology = Terminology(
        schema_version="0.1",
        terms=[
            TermEntry(canonical="bc", variants=["a"], confirmed=True),
            TermEntry(canonical="X", variants=["b"], confirmed=True),
        ],
    )

    result = normalize_transcript("a", terminology)

    assert result.text == "bc"
    assert len(result.corrections) == 1
