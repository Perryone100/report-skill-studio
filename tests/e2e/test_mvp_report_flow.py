from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient


def _all_text(value: Any) -> str:
    """Flatten structured report text without depending on its visual layout."""

    return json.dumps(value, ensure_ascii=False)


def test_mvp_report_lifecycle_is_local_validated_and_immutable(
    client: TestClient,
) -> None:
    skills_response = client.get("/api/skills")
    assert skills_response.status_code == 200
    default_skill = next(
        skill
        for skill in skills_response.json()
        if skill["id"] == "default-weekly-meeting"
    )
    assert default_skill["version"] == "0.2.1"
    assert default_skill["locale"] == "zh-CN"

    providers_response = client.get("/api/providers")
    assert providers_response.status_code == 200
    assert providers_response.json() == [
        {
            "id": "mock",
            "name": "本地演示模型",
            "model": "deterministic-mock",
            "local": True,
            "configured": True,
        }
    ]

    project_response = client.post(
        "/api/projects",
        json={"name": "产品研发", "description": "完全虚构的 MVP 端到端验收项目"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    report_response = client.post(
        "/api/reports",
        json={
            "project_id": project_id,
            "title": "产品研发周会纪要",
            "transcript": (
                "本周任务看版已完成缺陷收敛，星云计划项目进入验收；"
                "下周继续推进功能模块联调。"
            ),
            "skill_id": default_skill["id"],
        },
    )
    assert report_response.status_code == 201
    created_report = report_response.json()
    assert created_report["status"] == "draft"
    assert created_report["content"] == {}
    report_id = created_report["id"]

    generation_response = client.post(
        f"/api/reports/{report_id}/generate",
        json={"provider_id": "mock"},
    )
    assert generation_response.status_code == 200
    generation_job = generation_response.json()
    assert generation_job["status"] == "succeeded"
    assert generation_job["progress"] == 100
    assert generation_job["input"] == {
        "report_id": report_id,
        "provider_id": "mock",
        "skill_id": default_skill["id"],
    }
    corrections = {
        (item["original"], item["canonical"])
        for item in generation_job["result"]["corrections"]
    }
    assert corrections == {
        ("任务看版", "任务看板"),
        ("星云计划项目", "星云项目"),
    }

    job_response = client.get(f"/api/jobs/{generation_job['id']}")
    assert job_response.status_code == 200
    assert job_response.json() == generation_job

    generated_response = client.get(f"/api/reports/{report_id}")
    assert generated_response.status_code == 200
    generated_report = generated_response.json()
    assert generated_report["version"] == 2
    generated_text = _all_text(generated_report["content"])
    assert "任务看板" in generated_text
    assert "星云项目" in generated_text
    assert "任务看版" not in generated_text
    assert "星云计划" not in generated_text

    validation_response = client.get(f"/api/reports/{report_id}/validation")
    assert validation_response.status_code == 200
    assert validation_response.json() == {"valid": True, "issues": []}

    preview_response = client.get(f"/api/reports/{report_id}/preview")
    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"].startswith("text/html")
    assert "产品研发周会纪要" in preview_response.text
    assert "任务看板" in preview_response.text
    assert "星云项目" in preview_response.text
    for internal_label in (
        "图文结合版",
        "内容来源",
        "汇报口径",
        "输出形式",
        "AI生成",
    ):
        assert internal_label not in preview_response.text

    confirmation_response = client.post(f"/api/reports/{report_id}/confirm")
    assert confirmation_response.status_code == 200
    confirmed_report = confirmation_response.json()
    assert confirmed_report["status"] == "confirmed"
    assert confirmed_report["version"] == generated_report["version"]

    edit_response = client.patch(
        f"/api/reports/{report_id}",
        json={
            "title": "不应保存的标题",
            "content": {"title": "不应保存的内容"},
        },
    )
    assert edit_response.status_code == 409
    assert edit_response.json()["detail"] == "confirmed reports are immutable"

    persisted_response = client.get(f"/api/reports/{report_id}")
    assert persisted_response.status_code == 200
    persisted_report = persisted_response.json()
    assert persisted_report["status"] == "confirmed"
    assert persisted_report["title"] == generated_report["title"]
    assert persisted_report["content"] == generated_report["content"]
    assert persisted_report["version"] == generated_report["version"]
