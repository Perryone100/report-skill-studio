from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _generated_report(client: TestClient) -> tuple[str, str]:
    project = client.post(
        "/api/projects",
        json={"name": "研发/平台：周会", "description": "合成测试项目"},
    ).json()
    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "研发平台周会纪要",
            "transcript": "本周完成模块联调，下周推进验收，并关注资源协调风险。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()
    generated = client.post(
        f"/api/reports/{report['id']}/generate",
        json={"provider_id": "mock"},
    )
    assert generated.status_code == 200
    assert generated.json()["result"]["markdown"]["status"] == "synced"
    return project["id"], report["id"]


def test_markdown_library_uses_plain_project_folders_and_obsidian_markdown(
    client: TestClient,
) -> None:
    _, report_id = _generated_report(client)

    status = client.get(f"/api/reports/{report_id}/markdown")
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "synced"
    assert payload["relative_path"].endswith(".md")
    assert "/" in payload["relative_path"]

    markdown_path = Path(payload["file_path"])
    assert markdown_path.is_file()
    assert {path.suffix for path in markdown_path.parent.iterdir()} == {".md"}
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "report_skill_studio: true" in markdown
    assert f'report_id: "{report_id}"' in markdown
    assert "# 研发平台周会纪要" in markdown
    assert "> [!summary] 执行摘要" in markdown
    assert "## 01 本周重点项目" in markdown
    assert "| 工作项 | 本周进展 | 当前状态 | 下一步 |" in markdown
    assert "> [!warning]" in markdown


def test_same_day_title_collision_is_reflected_in_report_and_markdown(
    client: TestClient,
) -> None:
    project = client.post(
        "/api/projects",
        json={"name": "同名报告测试", "description": "合成测试项目"},
    ).json()

    def generate() -> dict[str, object]:
        report = client.post(
            "/api/reports",
            json={
                "project_id": project["id"],
                "title": "周会纪要",
                "transcript": "本周完成联调，下周继续验收，并跟踪资源协调风险。",
                "skill_id": "default-weekly-meeting",
            },
        ).json()
        response = client.post(
            f"/api/reports/{report['id']}/generate",
            json={"provider_id": "mock"},
        )
        assert response.status_code == 200
        return client.get(f"/api/reports/{report['id']}").json()

    first = generate()
    second = generate()
    first_sync = client.get(f"/api/reports/{first['id']}/markdown").json()
    second_sync = client.get(f"/api/reports/{second['id']}/markdown").json()

    assert first["title"] == first["content"]["title"] == "周会纪要"
    assert second["title"] == second["content"]["title"] == "周会纪要-2"
    assert Path(first_sync["file_path"]).name.endswith(" 周会纪要.md")
    assert Path(second_sync["file_path"]).name.endswith(" 周会纪要-2.md")
    second_markdown = Path(second_sync["file_path"]).read_text(encoding="utf-8")
    assert 'title: "周会纪要-2"' in second_markdown
    assert "# 周会纪要-2" in second_markdown
    latest_checkpoint = client.get(f"/api/reports/{second['id']}/versions").json()[0]
    assert latest_checkpoint["title"] == "周会纪要-2"
    assert latest_checkpoint["content"]["title"] == "周会纪要-2"

    saved = client.patch(
        f"/api/reports/{second['id']}/draft",
        json={
            "title": second["title"],
            "transcript": second["transcript"],
            "content": second["content"],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["title"] == "周会纪要-2"
    assert client.get(f"/api/reports/{second['id']}/markdown").json()[
        "file_path"
    ] == second_sync["file_path"]
    assert len(list(Path(second_sync["file_path"]).parent.glob("*.md"))) == 2


def test_external_markdown_edit_pauses_automatic_overwrite(client: TestClient) -> None:
    _, report_id = _generated_report(client)
    initial = client.get(f"/api/reports/{report_id}/markdown").json()
    markdown_path = Path(initial["file_path"])
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8") + "\n用户在 Obsidian 中补充的内容。\n",
        encoding="utf-8",
    )

    report = client.get(f"/api/reports/{report_id}").json()
    content = report["content"]
    content["executive_summary"] = "应用内的新摘要不应覆盖外部编辑。"
    saved = client.patch(
        f"/api/reports/{report_id}/draft",
        json={
            "title": report["title"],
            "transcript": report["transcript"],
            "content": content,
        },
    )
    assert saved.status_code == 200

    status = client.get(f"/api/reports/{report_id}/markdown").json()
    assert status["status"] == "conflict"
    assert "用户在 Obsidian 中补充的内容" in markdown_path.read_text(encoding="utf-8")
    assert client.post(f"/api/reports/{report_id}/markdown/sync").json()["status"] == "conflict"


def test_library_path_can_be_configured_but_rejects_unsafe_roots(
    client: TestClient,
    tmp_path: Path,
) -> None:
    custom_root = tmp_path / "Obsidian Vault" / "Report Skill Studio"
    configured = client.put(
        "/api/local-library",
        json={"root_path": str(custom_root)},
    )
    assert configured.status_code == 200
    assert configured.json() == {
        "root_path": str(custom_root),
        "configured": True,
        "exists": True,
        "writable": True,
    }
    assert list(custom_root.iterdir()) == []

    assert client.put(
        "/api/local-library", json={"root_path": "relative/path"}
    ).status_code == 422
    assert client.put("/api/local-library", json={"root_path": "/"}).status_code == 422


def test_confirmed_report_downloads_standalone_html(client: TestClient) -> None:
    _, report_id = _generated_report(client)
    assert client.post(f"/api/reports/{report_id}/confirm").status_code == 200

    exported = client.post(f"/api/reports/{report_id}/export/html")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/html")
    assert "attachment" in exported.headers["content-disposition"]
    assert "filename*=UTF-8''" in exported.headers["content-disposition"]
    assert "研发平台周会纪要" in exported.text
