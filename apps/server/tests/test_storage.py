import json
import sqlite3
from pathlib import Path

import pytest

from report_skill_server.models import ReportStatus
from report_skill_server.storage import SQLiteStore


def test_existing_version_table_is_migrated_with_snapshot_fields(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    timestamp = "2026-08-24T10:00:00+00:00"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE reports (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
                transcript TEXT NOT NULL, skill_id TEXT NOT NULL, content_json TEXT NOT NULL,
                status TEXT NOT NULL, version INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE report_versions (
                id TEXT PRIMARY KEY, report_id TEXT NOT NULL, version INTEGER NOT NULL,
                content_json TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(report_id, version)
            );
            """
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
            ("project-1", "项目", "", timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "report-1", "project-1", "旧报告", "旧逐字稿",
                "default-weekly-meeting", json.dumps({"title": "内容"}),
                "draft", 1, timestamp, timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO report_versions VALUES (?, ?, ?, ?, ?, ?)",
            ("version-1", "report-1", 1, json.dumps({"title": "内容"}), "created", timestamp),
        )

    store = SQLiteStore(database)

    version = store.get_report_version("report-1", 1)
    assert version.title == "旧报告"
    assert version.transcript == "旧逐字稿"


def test_report_versions_are_monotonic(store: SQLiteStore) -> None:
    project = store.create_project("项目")
    report = store.create_report(
        project_id=project.id,
        title="报告",
        transcript="逐字稿",
        skill_id="default-weekly-meeting",
    )

    updated = store.update_report(report.id, content={"title": "v2"})
    updated_again = store.update_report(report.id, content={"title": "v3"})

    assert updated.version == 2
    assert updated_again.version == 3


def test_empty_report_cannot_be_confirmed(store: SQLiteStore) -> None:
    project = store.create_project("项目")
    report = store.create_report(
        project_id=project.id,
        title="报告",
        transcript="逐字稿",
        skill_id="default-weekly-meeting",
    )

    with pytest.raises(ValueError, match="empty report"):
        store.confirm_report(report.id)


def test_autosave_persists_working_copy_without_creating_versions(
    store: SQLiteStore,
) -> None:
    project = store.create_project("项目")
    report = store.create_report(
        project_id=project.id,
        title="报告",
        transcript="原始逐字稿",
        skill_id="default-weekly-meeting",
    )

    saved = store.save_report_draft(
        report.id,
        title="自动保存标题",
        transcript="已修订逐字稿",
        content={"title": "自动保存内容"},
    )

    assert saved.version == 1
    assert saved.title == "自动保存标题"
    assert saved.transcript == "已修订逐字稿"
    assert saved.content == {"title": "自动保存内容"}
    assert [version.version for version in store.list_report_versions(report.id)] == [1]


def test_restoring_confirmed_version_creates_new_draft(store: SQLiteStore) -> None:
    project = store.create_project("项目")
    report = store.create_report(
        project_id=project.id,
        title="报告",
        transcript="逐字稿",
        skill_id="default-weekly-meeting",
    )
    checkpoint = store.update_report(
        report.id,
        title="正式标题",
        transcript="正式逐字稿",
        content={"title": "正式内容"},
        reason="edited",
    )
    store.confirm_report(report.id)

    restored = store.restore_report_version(report.id, checkpoint.version)

    assert restored.id != report.id
    assert restored.status is ReportStatus.DRAFT
    assert restored.title == "正式标题"
    assert restored.transcript == "正式逐字稿"
    assert restored.content == {"title": "正式内容"}
    assert store.get_report(report.id).status is ReportStatus.CONFIRMED
