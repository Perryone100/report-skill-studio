from fastapi.testclient import TestClient

from report_skill_server.main import get_provider_registry
from report_skill_server.providers import MockChatProvider
from report_skill_server.services import ProviderRegistry


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_report_lifecycle(client: TestClient) -> None:
    project_response = client.post(
        "/api/projects",
        json={"name": "产品研发", "description": "虚构的周会纪要示例"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    report_response = client.post(
        "/api/reports",
        json={
            "project_id": project_id,
            "title": "产品研发周会纪要",
            "transcript": "本周完成了逐字稿导入，下周继续联调。",
            "skill_id": "default-weekly-meeting",
        },
    )
    assert report_response.status_code == 201
    report_id = report_response.json()["id"]

    generation_response = client.post(
        f"/api/reports/{report_id}/generate",
        json={"provider_id": "mock"},
    )
    assert generation_response.status_code == 200
    assert generation_response.json()["status"] == "succeeded"

    fetched = client.get(f"/api/reports/{report_id}").json()
    assert fetched["version"] == 2
    assert fetched["content"]["title"] == "产品研发周会纪要"

    validation = client.get(f"/api/reports/{report_id}/validation")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    preview = client.get(f"/api/reports/{report_id}/preview")
    assert preview.status_code == 200
    assert "产品研发周会纪要" in preview.text
    assert "图文结合版" not in preview.text

    confirmation = client.post(f"/api/reports/{report_id}/confirm")
    assert confirmation.status_code == 200
    assert confirmation.json()["status"] == "confirmed"

    immutable = client.patch(
        f"/api/reports/{report_id}",
        json={"content": {"title": "should fail"}},
    )
    assert immutable.status_code == 409


def test_draft_autosave_does_not_create_versions_and_restore_is_recoverable(
    client: TestClient,
) -> None:
    project = client.post("/api/projects", json={"name": "自动保存测试"}).json()
    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "原始标题",
            "transcript": "本周完成自动保存功能，下周验证历史版本恢复。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()
    report_id = report["id"]
    generated = client.post(
        f"/api/reports/{report_id}/generate", json={"provider_id": "mock"}
    )
    assert generated.status_code == 200
    generated_report = client.get(f"/api/reports/{report_id}").json()
    generated_summary = generated_report["content"]["executive_summary"]

    changed_content = dict(generated_report["content"])
    changed_content["executive_summary"] = "这是自动保存后的工作副本。"
    autosaved = client.patch(
        f"/api/reports/{report_id}/draft",
        json={
            "title": "自动保存标题",
            "transcript": "",
            "content": changed_content,
        },
    )
    assert autosaved.status_code == 200
    assert autosaved.json()["version"] == 2
    assert autosaved.json()["transcript"] == ""

    versions = client.get(f"/api/reports/{report_id}/versions")
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [2, 1]
    assert versions.json()[0]["reason"].startswith("generated:")

    restored = client.post(f"/api/reports/{report_id}/versions/2/restore")
    assert restored.status_code == 200
    assert restored.json()["version"] == 3
    assert restored.json()["title"] == "原始标题"
    assert restored.json()["content"]["executive_summary"] == generated_summary
    assert [item["version"] for item in client.get(
        f"/api/reports/{report_id}/versions"
    ).json()] == [3, 2, 1]


def test_missing_project_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/reports",
        json={
            "project_id": "missing",
            "title": "报告",
            "transcript": "有效逐字稿",
        },
    )
    assert response.status_code == 404


def test_lists_bundled_skills(client: TestClient) -> None:
    response = client.get("/api/skills")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "default-weekly-meeting"


def test_only_confirmed_corrections_enter_memory(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "项目"}).json()
    rejected = client.post(
        "/api/memory/terms",
        json={
            "project_id": project["id"],
            "source_value": "任务看版",
            "normalized_value": "任务看板",
            "scope": "project",
            "confirmed": False,
        },
    )
    assert rejected.status_code == 422

    created = client.post(
        "/api/memory/terms",
        json={
            "project_id": project["id"],
            "source_value": "任务看版",
            "normalized_value": "任务看板",
            "scope": "project",
            "confirmed": True,
        },
    )
    assert created.status_code == 201
    assert created.json()["confirmed"] is True

    memories = client.get(
        "/api/memory/terms", params={"project_id": project["id"]}
    ).json()
    assert memories[0]["normalized_value"] == "任务看板"


def test_project_correction_memory_can_be_updated_and_deleted(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "项目"}).json()
    payload = {
        "project_id": project["id"],
        "source_value": "模块爱",
        "normalized_value": "模块 A",
        "scope": "project",
        "confirmed": True,
    }
    created = client.post("/api/memory/terms", json=payload)
    assert created.status_code == 201

    updated = client.post(
        "/api/memory/terms",
        json={**payload, "normalized_value": "功能模块 A"},
    )
    assert updated.status_code == 201
    assert updated.json()["id"] == created.json()["id"]
    assert updated.json()["normalized_value"] == "功能模块 A"

    memories = client.get(
        "/api/memory/terms", params={"project_id": project["id"]}
    ).json()
    assert [item for item in memories if item["source_value"] == "模块爱"] == [
        updated.json()
    ]

    deleted = client.delete(f"/api/memory/terms/{created.json()['id']}")
    assert deleted.status_code == 204
    assert client.delete(f"/api/memory/terms/{created.json()['id']}").status_code == 404


def test_generation_normalizes_confirmed_skill_terms(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "项目"}).json()
    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "术语检查",
            "transcript": "任务看版已完成更新，星云计划项目进入验收。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()

    job = client.post(
        f"/api/reports/{report['id']}/generate", json={"provider_id": "mock"}
    ).json()

    assert job["status"] == "succeeded"
    assert {item["canonical"] for item in job["result"]["corrections"]} == {
        "任务看板",
        "星云项目",
    }
    generated = client.get(f"/api/reports/{report['id']}").json()
    assert "任务看板" in generated["content"]["executive_summary"]
    assert "星云项目" in generated["content"]["executive_summary"]


def test_project_memory_overrides_bundled_term(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "项目"}).json()
    memory = client.post(
        "/api/memory/terms",
        json={
            "project_id": project["id"],
            "source_value": "任务看版",
            "normalized_value": "团队看板",
            "scope": "project",
            "confirmed": True,
        },
    )
    assert memory.status_code == 201
    later_global_memory = client.post(
        "/api/memory/terms",
        json={
            "project_id": None,
            "source_value": "任务看版",
            "normalized_value": "全局看板",
            "scope": "global",
            "confirmed": True,
        },
    )
    assert later_global_memory.status_code == 201

    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "项目术语",
            "transcript": "任务看版已完成更新。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()
    job = client.post(
        f"/api/reports/{report['id']}/generate", json={"provider_id": "mock"}
    ).json()

    assert job["status"] == "succeeded"
    assert job["result"]["corrections"][0]["canonical"] == "团队看板"
    generated = client.get(f"/api/reports/{report['id']}").json()
    assert "团队看板" in generated["content"]["executive_summary"]
    validation = client.get(f"/api/reports/{report['id']}/validation").json()
    assert validation["valid"] is True
    assert validation["issues"] == []


def test_project_memory_can_override_a_bundled_canonical_term(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "项目"}).json()
    memory = client.post(
        "/api/memory/terms",
        json={
            "project_id": project["id"],
            "source_value": "OCR",
            "normalized_value": "视觉识别模块",
            "scope": "project",
            "confirmed": True,
        },
    )
    assert memory.status_code == 201
    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "术语覆盖",
            "transcript": "OCR 已完成联调。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()

    job = client.post(
        f"/api/reports/{report['id']}/generate", json={"provider_id": "mock"}
    ).json()

    assert job["status"] == "succeeded"
    generated = client.get(f"/api/reports/{report['id']}").json()
    assert "视觉识别模块" in generated["content"]["executive_summary"]


def test_rule_issues_are_saved_for_human_review(client: TestClient) -> None:
    class ForbiddenPhraseProvider(MockChatProvider):
        id = "reviewable"

        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            content = super().generate(**kwargs)
            content["executive_summary"] += " 图文结合版"
            return content

    client.app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry(
        [ForbiddenPhraseProvider()]
    )
    project = client.post("/api/projects", json={"name": "项目"}).json()
    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "待人工修订",
            "transcript": "本周完成联调。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()

    job = client.post(
        f"/api/reports/{report['id']}/generate",
        json={"provider_id": "reviewable"},
    )
    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"
    assert job.json()["result"]["validation"]["valid"] is True
    assert job.json()["result"]["validation"]["issues"][0]["severity"] == "warning"

    saved = client.get(f"/api/reports/{report['id']}").json()
    assert "图文结合版" in saved["content"]["executive_summary"]
    confirmation = client.post(f"/api/reports/{report['id']}/confirm")
    assert confirmation.status_code == 200


def test_generation_only_sends_relevant_terminology_hints(client: TestClient) -> None:
    class PromptCaptureProvider(MockChatProvider):
        id = "prompt-capture"

        def __init__(self) -> None:
            self.prompt = ""

        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            self.prompt = kwargs["prompt"]
            return super().generate(**kwargs)

    provider = PromptCaptureProvider()
    client.app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry(
        [provider]
    )
    project = client.post("/api/projects", json={"name": "项目"}).json()
    for source, normalized in (
        ("模块爱", "功能模块 A"),
        ("完全无关错词", "完全无关标准词"),
    ):
        response = client.post(
            "/api/memory/terms",
            json={
                "project_id": project["id"],
                "source_value": source,
                "normalized_value": normalized,
                "scope": "project",
                "confirmed": True,
            },
        )
        assert response.status_code == 201

    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "提示词成本检查",
            "transcript": "模块爱已经完成联调。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()
    response = client.post(
        f"/api/reports/{report['id']}/generate",
        json={"provider_id": provider.id},
    )

    assert response.status_code == 200
    assert "模块爱 → 功能模块 A" in provider.prompt
    assert "完全无关错词" not in provider.prompt
