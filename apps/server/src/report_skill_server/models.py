from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class ReportStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MemoryScope(StrEnum):
    GLOBAL = "global"
    PROJECT = "project"
    TEMPORARY = "temporary"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime
    updated_at: datetime


class ReportCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    transcript: str = Field(min_length=1)
    skill_id: str = "default-weekly-meeting"


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    transcript: str | None = None
    content: dict[str, Any] | None = None


class ReportDraftSave(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    transcript: str
    content: dict[str, Any]


class Report(BaseModel):
    id: str
    project_id: str
    title: str
    transcript: str
    skill_id: str
    content: dict[str, Any]
    status: ReportStatus
    version: int
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class ReportVersion(BaseModel):
    id: str
    report_id: str
    version: int
    title: str
    transcript: str
    content: dict[str, Any]
    reason: str
    created_at: datetime


class GenerateReportRequest(BaseModel):
    provider_id: str = "mock"


class Job(BaseModel):
    id: str
    kind: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    input: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ProviderInfo(BaseModel):
    id: str
    name: str
    model: str
    local: bool
    configured: bool


class SkillInfo(BaseModel):
    id: str
    name: str
    version: str
    description: str
    locale: str
    source: Literal["bundled", "user"] = "bundled"
    can_delete: bool = False


class LocalLibraryUpdate(BaseModel):
    root_path: str = Field(min_length=1, max_length=2000)


class LocalLibraryInfo(BaseModel):
    root_path: str
    configured: bool
    exists: bool
    writable: bool


class MarkdownSyncResult(BaseModel):
    status: Literal["synced", "unsynced", "conflict", "missing", "no_content", "error"]
    root_path: str
    relative_path: str | None = None
    file_path: str | None = None
    message: str
    synced_at: datetime | None = None


class TerminologyMemoryCreate(BaseModel):
    project_id: str | None = None
    source_value: str = Field(min_length=1, max_length=120)
    normalized_value: str = Field(min_length=1, max_length=120)
    scope: MemoryScope = MemoryScope.PROJECT
    confirmed: Literal[True]


class TerminologyMemory(BaseModel):
    id: str
    project_id: str | None = None
    source_value: str
    normalized_value: str
    scope: MemoryScope
    confirmed: bool
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class SessionInfo(BaseModel):
    request_token: str
