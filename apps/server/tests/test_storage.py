import pytest

from report_skill_server.storage import SQLiteStore


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
