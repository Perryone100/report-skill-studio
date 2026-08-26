from __future__ import annotations

from datetime import date
from typing import Any


class MockChatProvider:
    """Deterministic local provider used for development and contract tests."""

    id = "mock"
    name = "本地演示模型"
    model = "deterministic-mock"
    local = True

    def generate(
        self,
        *,
        transcript: str,
        title: str,
        instructions: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        excerpt = " ".join(transcript.strip().split())[:180]
        return {
            "title": title,
            "meeting_date": date.today().isoformat(),
            "executive_summary": excerpt,
            "summary_cards": [
                {"label": "本周阶段", "value": "待人工确认", "tone": "info"},
                {"label": "核心进展", "value": "已完成逐字稿导入", "tone": "success"},
                {"label": "重点风险", "value": "尚未调用真实模型", "tone": "warning"},
            ],
            "sections": [
                {
                    "id": "key_project_details",
                    "title": "本周重点项目",
                    "blocks": [
                        {
                            "type": "status_cards",
                            "cards": [
                                {
                                    "title": "逐字稿整理",
                                    "status": "待确认",
                                    "details": [
                                        "已完成逐字稿导入。",
                                        "下一步需人工核对事实、日期与术语。",
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": "this_week_progress",
                    "title": "本周工作进展",
                    "blocks": [
                        {
                            "type": "project_table",
                            "columns": ["工作项", "本周进展", "当前状态", "下一步"],
                            "rows": [
                                [
                                    "逐字稿整理",
                                    "已完成内容导入",
                                    "待确认",
                                    "人工核对事实、日期与术语",
                                ]
                            ],
                        }
                    ],
                },
                {
                    "id": "next_week_plan",
                    "title": "下周重点计划",
                    "blocks": [
                        {
                            "type": "bullet_list",
                            "items": ["根据人工确认结果补充明确的下一步计划。"],
                        }
                    ],
                },
                {
                    "id": "risks_and_coordination",
                    "title": "风险与待协调事项",
                    "blocks": [
                        {
                            "type": "callout",
                            "title": "内容核对",
                            "text": "逐字稿中的事实、日期与术语尚需人工确认。",
                            "tone": "warning",
                        }
                    ],
                },
            ],
        }
