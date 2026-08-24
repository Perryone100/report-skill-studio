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
    TerminologyMemory,
    new_id,
    utc_now,
)


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    transcript TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    content_json TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_versions (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(report_id, version)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL,
    input_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS terminology_memory (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    source_value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    scope TEXT NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


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
                    (id, project_id, title, transcript, skill_id, content_json, status, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            self._insert_version(connection, report_id, 1, content, "created", now)
        return self.get_report(report_id)

    def list_reports(self, project_id: str | None = None) -> list[Report]:
        query = "SELECT * FROM reports"
        params: tuple[Any, ...] = ()
        if project_id is not None:
            query += " WHERE project_id = ?"
            params = (project_id,)
        query += " ORDER BY updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._report_from_row(row) for row in rows]

    def get_report(self, report_id: str) -> Report:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"report not found: {report_id}")
        return self._report_from_row(row)

    def update_report(
        self,
        report_id: str,
        *,
        title: str | None = None,
        content: dict[str, Any] | None = None,
        reason: str = "edited",
    ) -> Report:
        report = self.get_report(report_id)
        if report.status is ReportStatus.CONFIRMED:
            raise ValueError("confirmed reports are immutable")

        next_title = title if title is not None else report.title
        next_content = content if content is not None else report.content
        next_version = report.version + 1
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE reports SET title = ?, content_json = ?, version = ?, updated_at = ? WHERE id = ?",
                (
                    next_title,
                    json.dumps(next_content, ensure_ascii=False),
                    next_version,
                    now.isoformat(),
                    report_id,
                ),
            )
            self._insert_version(connection, report_id, next_version, next_content, reason, now)
        return self.get_report(report_id)

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
        memory_id = new_id()
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO terminology_memory
                    (id, project_id, source_value, normalized_value, scope, confirmed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    memory_id,
                    project_id,
                    source_value.strip(),
                    normalized_value.strip(),
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

    @staticmethod
    def _insert_version(
        connection: sqlite3.Connection,
        report_id: str,
        version: int,
        content: dict[str, Any],
        reason: str,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO report_versions (id, report_id, version, content_json, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id(),
                report_id,
                version,
                json.dumps(content, ensure_ascii=False),
                reason,
                created_at.isoformat(),
            ),
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
