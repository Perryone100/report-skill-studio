from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    Job,
    JobStatus,
    MemoryScope,
    Project,
    Report,
    ReportStatus,
    ReportVersion,
    TerminologyMemory,
    new_id,
    utc_now,
)
from .storage_schema import SCHEMA


class NotFoundError(LookupError):
    pass


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            version_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(report_versions)").fetchall()
            }
            if "title" not in version_columns:
                connection.execute("ALTER TABLE report_versions ADD COLUMN title TEXT")
            if "transcript" not in version_columns:
                connection.execute("ALTER TABLE report_versions ADD COLUMN transcript TEXT")
            report_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(reports)").fetchall()
            }
            if "generated_at" not in report_columns:
                connection.execute("ALTER TABLE reports ADD COLUMN generated_at TEXT")
            connection.execute(
                """
                UPDATE report_versions
                SET title = COALESCE(
                    title,
                    (SELECT reports.title FROM reports WHERE reports.id = report_versions.report_id)
                ),
                    transcript = COALESCE(
                    transcript,
                    (SELECT reports.transcript FROM reports WHERE reports.id = report_versions.report_id)
                )
                WHERE title IS NULL OR transcript IS NULL
                """
            )
            connection.execute(
                """
                UPDATE reports
                SET generated_at = COALESCE(
                    (
                        SELECT MAX(report_versions.created_at)
                        FROM report_versions
                        WHERE report_versions.report_id = reports.id
                          AND report_versions.reason LIKE 'generated:%'
                    ),
                    created_at
                )
                WHERE generated_at IS NULL
                """
            )

    def create_project(self, name: str, description: str = "") -> Project:
        project_id = new_id()
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, name, description, now.isoformat(), now.isoformat()),
            )
        return self.get_project(project_id)

    def list_projects(self) -> list[Project]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [self._project_from_row(row) for row in rows]

    def get_project(self, project_id: str) -> Project:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"project not found: {project_id}")
        return self._project_from_row(row)

    def delete_project(self, project_id: str) -> None:
        self.get_project(project_id)
        with self.connect() as connection:
            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def get_setting(self, key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        now = utc_now().isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def get_project_markdown_folder(self, project_id: str) -> str | None:
        self.get_project(project_id)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT folder_name FROM project_markdown_folders WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return None if row is None else str(row["folder_name"])

    def list_project_markdown_folders(self) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT project_id, folder_name FROM project_markdown_folders"
            ).fetchall()
        return {str(row["project_id"]): str(row["folder_name"]) for row in rows}

    def set_project_markdown_folder(self, project_id: str, folder_name: str) -> None:
        self.get_project(project_id)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO project_markdown_folders (project_id, folder_name)
                VALUES (?, ?)
                ON CONFLICT(project_id) DO UPDATE SET folder_name = excluded.folder_name
                """,
                (project_id, folder_name),
            )

    def get_report_markdown_file(self, report_id: str) -> dict[str, str] | None:
        self.get_report(report_id)
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT filename, content_hash, synced_at
                FROM report_markdown_files
                WHERE report_id = ?
                """,
                (report_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "filename": str(row["filename"]),
            "content_hash": str(row["content_hash"]),
            "synced_at": str(row["synced_at"]),
        }

    def set_report_markdown_file(
        self,
        report_id: str,
        *,
        filename: str,
        content_hash: str,
        synced_at: datetime,
    ) -> None:
        self.get_report(report_id)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO report_markdown_files (report_id, filename, content_hash, synced_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    filename = excluded.filename,
                    content_hash = excluded.content_hash,
                    synced_at = excluded.synced_at
                """,
                (report_id, filename, content_hash, synced_at.isoformat()),
            )

    def create_report(
        self,
        *,
        project_id: str,
        title: str,
        transcript: str,
        skill_id: str,
    ) -> Report:
        self.get_project(project_id)
        report_id = new_id()
        now = utc_now()
        content: dict[str, Any] = {}
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO reports
                    (id, project_id, title, transcript, skill_id, content_json, status, version, generated_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    project_id,
                    title,
                    transcript,
                    skill_id,
                    json.dumps(content, ensure_ascii=False),
                    ReportStatus.DRAFT.value,
                    1,
                    now.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            self._insert_version(
                connection,
                report_id,
                1,
                title,
                transcript,
                content,
                "created",
                now,
            )
        return self.get_report(report_id)

    def list_reports(self, project_id: str | None = None) -> list[Report]:
        query = "SELECT * FROM reports"
        params: tuple[Any, ...] = ()
        if project_id is not None:
            query += " WHERE project_id = ?"
            params = (project_id,)
        query += " ORDER BY generated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._report_from_row(row) for row in rows]

    def get_report(self, report_id: str) -> Report:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"report not found: {report_id}")
        return self._report_from_row(row)

    def delete_report(self, report_id: str) -> None:
        self.get_report(report_id)
        with self.connect() as connection:
            connection.execute("DELETE FROM reports WHERE id = ?", (report_id,))

    def update_report(
        self,
        report_id: str,
        *,
        title: str | None = None,
        transcript: str | None = None,
        content: dict[str, Any] | None = None,
        reason: str = "edited",
    ) -> Report:
        report = self.get_report(report_id)
        if report.status is ReportStatus.CONFIRMED:
            raise ValueError("confirmed reports are immutable")

        next_title = title if title is not None else report.title
        next_transcript = transcript if transcript is not None else report.transcript
        next_content = content if content is not None else report.content
        next_version = report.version + 1
        now = utc_now()
        next_generated_at = now if reason.startswith("generated:") else report.generated_at
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE reports
                SET title = ?, transcript = ?, content_json = ?, version = ?, generated_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_title,
                    next_transcript,
                    json.dumps(next_content, ensure_ascii=False),
                    next_version,
                    next_generated_at.isoformat(),
                    now.isoformat(),
                    report_id,
                ),
            )
            self._insert_version(
                connection,
                report_id,
                next_version,
                next_title,
                next_transcript,
                next_content,
                reason,
                now,
            )
        return self.get_report(report_id)

    def save_report_draft(
        self,
        report_id: str,
        *,
        title: str,
        transcript: str,
        content: dict[str, Any],
    ) -> Report:
        """Persist the working copy without creating a permanent version."""

        report = self.get_report(report_id)
        if report.status is ReportStatus.CONFIRMED:
            raise ValueError("confirmed reports are immutable")
        if (
            report.title == title
            and report.transcript == transcript
            and report.content == content
        ):
            return report

        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE reports
                SET title = ?, transcript = ?, content_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    transcript,
                    json.dumps(content, ensure_ascii=False),
                    now.isoformat(),
                    report_id,
                ),
            )
        return self.get_report(report_id)

    def align_report_document_title(self, report_id: str, title: str) -> Report:
        """Align the persisted report title with its allocated Markdown document name.

        Markdown filename allocation happens after structured generation, because the
        meeting date is part of the filename.  A same-day collision may therefore add
        a numeric suffix after the generated version already exists.  This narrowly
        scoped metadata update keeps the current report and the title in its current
        checkpoint consistent without creating a user-edit version.  Only the title
        field of that checkpoint is changed; later working-copy content is never
        copied into history.
        """

        report = self.get_report(report_id)
        next_content = dict(report.content)
        next_content["title"] = title
        if report.title == title and report.content == next_content:
            return report

        now = utc_now()
        encoded_content = json.dumps(next_content, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE reports
                SET title = ?, content_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, encoded_content, now.isoformat(), report_id),
            )
            snapshot = connection.execute(
                """
                SELECT content_json FROM report_versions
                WHERE report_id = ? AND version = ?
                """,
                (report_id, report.version),
            ).fetchone()
            if snapshot is not None:
                snapshot_content = json.loads(str(snapshot["content_json"]))
                if snapshot_content:
                    snapshot_content["title"] = title
                connection.execute(
                    """
                    UPDATE report_versions
                    SET title = ?, content_json = ?
                    WHERE report_id = ? AND version = ?
                    """,
                    (
                        title,
                        json.dumps(snapshot_content, ensure_ascii=False),
                        report_id,
                        report.version,
                    ),
                )
        return self.get_report(report_id)

    def list_report_versions(self, report_id: str) -> list[ReportVersion]:
        self.get_report(report_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM report_versions
                WHERE report_id = ?
                ORDER BY version DESC
                """,
                (report_id,),
            ).fetchall()
        return [self._report_version_from_row(row) for row in rows]

    def get_report_version(self, report_id: str, version: int) -> ReportVersion:
        self.get_report(report_id)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM report_versions WHERE report_id = ? AND version = ?",
                (report_id, version),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"report version not found: {report_id}@{version}")
        return self._report_version_from_row(row)

    def restore_report_version(self, report_id: str, version: int) -> Report:
        report = self.get_report(report_id)
        snapshot = self.get_report_version(report_id, version)
        if report.status is ReportStatus.CONFIRMED:
            restored = self.create_report(
                project_id=report.project_id,
                title=snapshot.title,
                transcript=snapshot.transcript,
                skill_id=report.skill_id,
            )
            return self.update_report(
                restored.id,
                title=snapshot.title,
                transcript=snapshot.transcript,
                content=snapshot.content,
                reason=f"restored:{report_id}@{version}",
            )
        return self.update_report(
            report_id,
            title=snapshot.title,
            transcript=snapshot.transcript,
            content=snapshot.content,
            reason=f"restored:{version}",
        )

    def confirm_report(self, report_id: str) -> Report:
        report = self.get_report(report_id)
        if not report.content:
            raise ValueError("an empty report cannot be confirmed")
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
                (ReportStatus.CONFIRMED.value, now.isoformat(), report_id),
            )
        return self.get_report(report_id)

    def create_job(self, kind: str, input_data: dict[str, Any]) -> Job:
        job_id = new_id()
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, kind, status, progress, input_json, result_json, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    job_id,
                    kind,
                    JobStatus.QUEUED.value,
                    0,
                    json.dumps(input_data, ensure_ascii=False),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Job:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"job not found: {job_id}")
        return self._job_from_row(row)

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus,
        progress: int,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Job:
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, progress = ?, result_json = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    progress,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                    now.isoformat(),
                    job_id,
                ),
            )
            if cursor.rowcount == 0:
                raise NotFoundError(f"job not found: {job_id}")
        return self.get_job(job_id)

    def create_terminology_memory(
        self,
        *,
        project_id: str | None,
        source_value: str,
        normalized_value: str,
        scope: MemoryScope,
    ) -> TerminologyMemory:
        if scope is MemoryScope.PROJECT and project_id is None:
            raise ValueError("project-scoped terminology requires project_id")
        if project_id is not None:
            self.get_project(project_id)
        source = source_value.strip()
        normalized = normalized_value.strip()
        if not source or not normalized:
            raise ValueError("terminology values must not be blank")
        if source.casefold() == normalized.casefold():
            raise ValueError("source and normalized terminology must be different")
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT id FROM terminology_memory
                WHERE project_id IS ? AND lower(source_value) = lower(?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (project_id, source),
            ).fetchone()
            if existing is not None:
                memory_id = existing["id"]
                connection.execute(
                    """
                    UPDATE terminology_memory
                    SET normalized_value = ?, scope = ?, confirmed = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (normalized, scope.value, now.isoformat(), memory_id),
                )
            else:
                memory_id = new_id()
                connection.execute(
                    """
                    INSERT INTO terminology_memory
                        (id, project_id, source_value, normalized_value, scope, confirmed, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        memory_id,
                        project_id,
                        source,
                        normalized,
                        scope.value,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
        return self.get_terminology_memory(memory_id)

    def get_terminology_memory(self, memory_id: str) -> TerminologyMemory:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM terminology_memory WHERE id = ?", (memory_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"terminology memory not found: {memory_id}")
        return self._memory_from_row(row)

    def list_terminology_memory(self, project_id: str | None = None) -> list[TerminologyMemory]:
        query = "SELECT * FROM terminology_memory"
        params: tuple[Any, ...] = ()
        if project_id is not None:
            query += " WHERE project_id IS NULL OR project_id = ?"
            params = (project_id,)
        query += " ORDER BY updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def delete_terminology_memory(self, memory_id: str) -> None:
        self.get_terminology_memory(memory_id)
        with self.connect() as connection:
            connection.execute("DELETE FROM terminology_memory WHERE id = ?", (memory_id,))

    @staticmethod
    def _insert_version(
        connection: sqlite3.Connection,
        report_id: str,
        version: int,
        title: str,
        transcript: str,
        content: dict[str, Any],
        reason: str,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO report_versions
                (id, report_id, version, title, transcript, content_json, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id(),
                report_id,
                version,
                title,
                transcript,
                json.dumps(content, ensure_ascii=False),
                reason,
                created_at.isoformat(),
            ),
        )

    @staticmethod
    def _report_version_from_row(row: sqlite3.Row) -> ReportVersion:
        return ReportVersion(
            id=row["id"],
            report_id=row["report_id"],
            version=row["version"],
            title=row["title"],
            transcript=row["transcript"],
            content=json.loads(row["content_json"]),
            reason=row["reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _report_from_row(row: sqlite3.Row) -> Report:
        return Report(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            transcript=row["transcript"],
            skill_id=row["skill_id"],
            content=json.loads(row["content_json"]),
            status=ReportStatus(row["status"]),
            version=row["version"],
            generated_at=datetime.fromisoformat(row["generated_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            kind=row["kind"],
            status=JobStatus(row["status"]),
            progress=row["progress"],
            input=json.loads(row["input_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> TerminologyMemory:
        return TerminologyMemory(
            id=row["id"],
            project_id=row["project_id"],
            source_value=row["source_value"],
            normalized_value=row["normalized_value"],
            scope=MemoryScope(row["scope"]),
            confirmed=bool(row["confirmed"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
