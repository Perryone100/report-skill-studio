from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient


def _project_with_report(client: TestClient) -> tuple[dict[str, object], dict[str, object], Path]:
    project = client.post(
        "/api/projects",
        json={"name": "隐私测试项目", "description": "完全虚构的测试数据"},
    ).json()
    report = client.post(
        "/api/reports",
        json={
            "project_id": project["id"],
            "title": "虚构周会纪要",
            "transcript": "本周完成虚构联调，下周继续虚构验收。",
            "skill_id": "default-weekly-meeting",
        },
    ).json()
    generated = client.post(
        f"/api/reports/{report['id']}/generate",
        json={"provider_id": "mock"},
    )
    assert generated.status_code == 200
    sync = client.get(f"/api/reports/{report['id']}/markdown").json()
    return project, client.get(f"/api/reports/{report['id']}").json(), Path(sync["file_path"])


def test_project_backup_contains_canonical_json_and_markdown_without_credentials(
    client: TestClient,
) -> None:
    project, report, _ = _project_with_report(client)
    client.post(
        "/api/memory/terms",
        json={
            "project_id": project["id"],
            "source_value": "错词",
            "normalized_value": "正确词",
            "scope": "project",
            "confirmed": True,
        },
    )

    response = client.get(f"/api/projects/{project['id']}/backup")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        assert "backup.json" in archive.namelist()
        assert any(name.startswith("markdown/") and name.endswith(".md") for name in archive.namelist())
        payload = json.loads(archive.read("backup.json"))
    assert payload["format"] == "report-skill-studio-project-backup"
    assert payload["project"]["id"] == project["id"]
    assert payload["reports"][0]["id"] == report["id"]
    assert payload["terminology_memory"][0]["normalized_value"] == "正确词"
    assert "api_key" not in json.dumps(payload)


def test_clear_history_removes_database_reports_and_unchanged_markdown(
    client: TestClient,
) -> None:
    project, _, markdown_path = _project_with_report(client)
    assert markdown_path.is_file()

    response = client.delete(f"/api/projects/{project['id']}/reports")

    assert response.status_code == 204
    assert client.get(f"/api/reports?project_id={project['id']}").json() == []
    assert not markdown_path.exists()
    assert client.get(f"/api/projects/{project['id']}").status_code == 200


def test_external_markdown_change_blocks_project_deletion(client: TestClient) -> None:
    project, report, markdown_path = _project_with_report(client)
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8") + "\n用户在 Obsidian 中的补充。\n",
        encoding="utf-8",
    )

    blocked = client.delete(f"/api/projects/{project['id']}")

    assert blocked.status_code == 409
    assert markdown_path.is_file()
    assert client.get(f"/api/projects/{project['id']}").status_code == 200
    assert client.get(f"/api/reports/{report['id']}").status_code == 200
