from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from .local_library import render_report_markdown, safe_path_component
from .models import utc_now
from .storage import SQLiteStore


@dataclass(frozen=True)
class ProjectBackup:
    filename: str
    content: bytes


def export_project_backup(store: SQLiteStore, project_id: str) -> ProjectBackup:
    """Create a portable, secret-free archive of one project's canonical data."""

    project = store.get_project(project_id)
    reports = store.list_reports(project_id)
    memories = [
        memory
        for memory in store.list_terminology_memory(project_id)
        if memory.project_id == project_id
    ]
    payload = {
        "format": "report-skill-studio-project-backup",
        "version": 1,
        "exported_at": utc_now().isoformat(),
        "project": project.model_dump(mode="json"),
        "reports": [
            {
                **report.model_dump(mode="json"),
                "versions": [
                    version.model_dump(mode="json")
                    for version in store.list_report_versions(report.id)
                ],
            }
            for report in reports
        ],
        "terminology_memory": [memory.model_dump(mode="json") for memory in memories],
    }

    buffer = BytesIO()
    used_markdown_names: set[str] = set()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "backup.json",
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        for report in reports:
            if not report.content:
                continue
            mapping = store.get_report_markdown_file(report.id)
            filename = mapping["filename"] if mapping else f"{safe_path_component(report.title, fallback=report.id)}.md"
            candidate = filename
            suffix = 2
            while candidate.casefold() in used_markdown_names:
                stem = filename[:-3] if filename.lower().endswith(".md") else filename
                candidate = f"{stem}-{suffix}.md"
                suffix += 1
            used_markdown_names.add(candidate.casefold())
            archive.writestr(
                f"markdown/{candidate}",
                render_report_markdown(report, project.name).encode("utf-8"),
            )

    project_name = safe_path_component(project.name, fallback="project", max_length=80)
    return ProjectBackup(
        filename=f"{project_name}-backup-{date.today().isoformat()}.zip",
        content=buffer.getvalue(),
    )
