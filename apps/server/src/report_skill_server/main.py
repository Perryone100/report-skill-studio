from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from report_renderer import PdfRenderingUnavailableError, ReportRendererError
from skill_engine import SkillLoadError

from . import __version__
from .config import Settings, get_settings
from .data_management import export_project_backup
from .local_library import LocalMarkdownLibrary
from .models import (
    GenerateReportRequest,
    HealthResponse,
    Job,
    LocalLibraryInfo,
    LocalLibraryUpdate,
    MarkdownSyncResult,
    Project,
    ProjectCreate,
    ProviderInfo,
    Report,
    ReportCreate,
    ReportDraftSave,
    ReportUpdate,
    ReportVersion,
    SkillInfo,
    TerminologyMemory,
    TerminologyMemoryCreate,
)
from .providers import MockChatProvider, OpenAICompatibleChatProvider, ProviderGenerationError
from .services import ProviderRegistry, ReportGenerationService, SkillRegistry
from .storage import NotFoundError, SQLiteStore


@lru_cache
def get_store() -> SQLiteStore:
    return SQLiteStore(get_settings().database_path)


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    return build_provider_registry(get_settings())


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    providers = [MockChatProvider()]
    for connection in settings.openai_compatible_connection_configs:
        providers.extend(
            OpenAICompatibleChatProvider(
                base_url=connection.base_url,
                api_key=connection.api_key.get_secret_value(),
                model=model,
                provider_id=f"openai-compatible:{connection.id}:{model}",
                provider_name=connection.name,
            )
            for model in connection.models
        )
    if (
        settings.openai_compatible_base_url
        and settings.openai_compatible_api_key
        and settings.openai_compatible_model_names
    ):
        providers.extend(
            [
                OpenAICompatibleChatProvider(
                    base_url=settings.openai_compatible_base_url,
                    api_key=settings.openai_compatible_api_key.get_secret_value(),
                    model=model,
                    provider_id=f"openai-compatible:{model}",
                )
                for model in settings.openai_compatible_model_names
            ]
        )
    return ProviderRegistry(providers)


@lru_cache
def get_skill_registry() -> SkillRegistry:
    settings = get_settings()
    return SkillRegistry(settings.skills_dir, settings.user_skills_dir)


def get_local_library(
    store: SQLiteStore = Depends(get_store),
) -> LocalMarkdownLibrary:
    return LocalMarkdownLibrary(store, get_settings().projects_dir)


def get_generation_service(
    store: SQLiteStore = Depends(get_store),
    providers: ProviderRegistry = Depends(get_provider_registry),
    skills: SkillRegistry = Depends(get_skill_registry),
    local_library: LocalMarkdownLibrary = Depends(get_local_library),
) -> ReportGenerationService:
    return ReportGenerationService(
        store,
        providers,
        skills,
        get_settings().artifacts_dir,
        local_library,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().ensure_directories()
    get_store().initialize()
    yield


def create_app() -> FastAPI:
    active_settings = get_settings()
    app = FastAPI(title=active_settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(version=__version__)

    @app.get("/api/local-library", response_model=LocalLibraryInfo)
    def get_local_library_info(
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> LocalLibraryInfo:
        return library.info()

    @app.put("/api/local-library", response_model=LocalLibraryInfo)
    def configure_local_library(
        payload: LocalLibraryUpdate,
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> LocalLibraryInfo:
        try:
            return library.configure(payload.root_path)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/projects", response_model=list[Project])
    def list_projects(store: SQLiteStore = Depends(get_store)) -> list[Project]:
        return store.list_projects()

    @app.post("/api/projects", response_model=Project, status_code=201)
    def create_project(payload: ProjectCreate, store: SQLiteStore = Depends(get_store)) -> Project:
        return store.create_project(payload.name, payload.description)

    @app.get("/api/projects/{project_id}", response_model=Project)
    def get_project(project_id: str, store: SQLiteStore = Depends(get_store)) -> Project:
        try:
            return store.get_project(project_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/backup")
    def backup_project(
        project_id: str,
        store: SQLiteStore = Depends(get_store),
    ) -> Response:
        try:
            backup = export_project_backup(store, project_id)
            encoded_filename = quote(backup.filename)
            return Response(
                backup.content,
                media_type="application/zip",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=project-backup.zip; "
                        f"filename*=UTF-8''{encoded_filename}"
                    )
                },
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/projects/{project_id}/reports", status_code=204)
    def clear_project_reports(
        project_id: str,
        store: SQLiteStore = Depends(get_store),
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> Response:
        try:
            library.delete_project_files(project_id)
            for report in store.list_reports(project_id):
                store.delete_report(report.id)
            return Response(status_code=204)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/api/projects/{project_id}", status_code=204)
    def delete_project(
        project_id: str,
        store: SQLiteStore = Depends(get_store),
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> Response:
        try:
            library.delete_project_files(project_id)
            store.delete_project(project_id)
            return Response(status_code=204)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/reports", response_model=list[Report])
    def list_reports(
        project_id: str | None = Query(default=None),
        store: SQLiteStore = Depends(get_store),
    ) -> list[Report]:
        return store.list_reports(project_id)

    @app.post("/api/reports", response_model=Report, status_code=201)
    def create_report(payload: ReportCreate, store: SQLiteStore = Depends(get_store)) -> Report:
        try:
            return store.create_report(**payload.model_dump())
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/reports/{report_id}", response_model=Report)
    def get_report(report_id: str, store: SQLiteStore = Depends(get_store)) -> Report:
        try:
            return store.get_report(report_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/reports/{report_id}", status_code=204)
    def delete_report(
        report_id: str,
        store: SQLiteStore = Depends(get_store),
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> Response:
        try:
            library.delete_report_file(report_id)
            store.delete_report(report_id)
            return Response(status_code=204)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch("/api/reports/{report_id}", response_model=Report)
    def update_report(
        report_id: str,
        payload: ReportUpdate,
        store: SQLiteStore = Depends(get_store),
    ) -> Report:
        try:
            return store.update_report(report_id, **payload.model_dump(exclude_none=True))
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch("/api/reports/{report_id}/draft", response_model=Report)
    def save_report_draft(
        report_id: str,
        payload: ReportDraftSave,
        store: SQLiteStore = Depends(get_store),
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> Report:
        try:
            store.save_report_draft(report_id, **payload.model_dump())
            library.sync(report_id)
            return store.get_report(report_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/reports/{report_id}/versions", response_model=list[ReportVersion])
    def list_report_versions(
        report_id: str,
        store: SQLiteStore = Depends(get_store),
    ) -> list[ReportVersion]:
        try:
            return store.list_report_versions(report_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/reports/{report_id}/versions/{version}/restore",
        response_model=Report,
    )
    def restore_report_version(
        report_id: str,
        version: int,
        store: SQLiteStore = Depends(get_store),
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> Report:
        try:
            report = store.restore_report_version(report_id, version)
            library.sync(report.id)
            return report
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/reports/{report_id}/confirm", response_model=Report)
    def confirm_report(
        report_id: str,
        service: ReportGenerationService = Depends(get_generation_service),
    ) -> Report:
        try:
            return service.confirm(report_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/reports/{report_id}/validation")
    def validate_report(
        report_id: str,
        service: ReportGenerationService = Depends(get_generation_service),
    ) -> dict[str, object]:
        try:
            return service.validate(report_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/reports/{report_id}/preview", response_class=HTMLResponse)
    def preview_report(
        report_id: str,
        service: ReportGenerationService = Depends(get_generation_service),
    ) -> HTMLResponse:
        try:
            return HTMLResponse(service.preview_html(report_id))
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ReportRendererError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/reports/{report_id}/markdown", response_model=MarkdownSyncResult)
    def get_report_markdown_status(
        report_id: str,
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> MarkdownSyncResult:
        try:
            return library.status(report_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/reports/{report_id}/markdown/sync", response_model=MarkdownSyncResult)
    def sync_report_markdown(
        report_id: str,
        library: LocalMarkdownLibrary = Depends(get_local_library),
    ) -> MarkdownSyncResult:
        try:
            return library.sync(report_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/reports/{report_id}/export", response_class=FileResponse)
    def export_report(
        report_id: str,
        service: ReportGenerationService = Depends(get_generation_service),
    ) -> FileResponse:
        try:
            artifact = service.export_pdf(report_id)
            return FileResponse(
                artifact,
                media_type="application/pdf",
                filename=service.download_filename_for(report_id, "pdf"),
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PdfRenderingUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ReportRendererError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/reports/{report_id}/export/html")
    def export_report_html(
        report_id: str,
        service: ReportGenerationService = Depends(get_generation_service),
    ) -> Response:
        try:
            html, filename = service.export_html(report_id)
            return Response(
                content=html,
                media_type="text/html; charset=utf-8",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=report.html; filename*=UTF-8''{quote(filename)}"
                    )
                },
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReportRendererError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/reports/{report_id}/generate", response_model=Job)
    def generate_report(
        report_id: str,
        payload: GenerateReportRequest,
        service: ReportGenerationService = Depends(get_generation_service),
    ) -> Job:
        try:
            return service.generate(report_id, payload.provider_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ProviderGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}", response_model=Job)
    def get_job(job_id: str, store: SQLiteStore = Depends(get_store)) -> Job:
        try:
            return store.get_job(job_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/providers", response_model=list[ProviderInfo])
    def list_providers(
        providers: ProviderRegistry = Depends(get_provider_registry),
    ) -> list[ProviderInfo]:
        return providers.list()

    @app.get("/api/skills", response_model=list[SkillInfo])
    def list_skills(skills: SkillRegistry = Depends(get_skill_registry)) -> list[SkillInfo]:
        try:
            return skills.list()
        except SkillLoadError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/skills/install", response_model=SkillInfo, status_code=201)
    async def install_skill(
        request: Request,
        replace: bool = Query(default=False),
        skills: SkillRegistry = Depends(get_skill_registry),
        store: SQLiteStore = Depends(get_store),
    ) -> SkillInfo:
        content_length = request.headers.get("content-length")
        try:
            declared_size = int(content_length) if content_length else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from exc
        if declared_size is not None and declared_size > SkillRegistry.MAX_ARCHIVE_BYTES:
            raise HTTPException(status_code=413, detail="Skill ZIP exceeds the 8 MB upload limit")
        try:
            return skills.install_archive(
                await request.body(),
                replace_existing=replace,
                protected_skill_ids={report.skill_id for report in store.list_reports()},
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (SkillLoadError, ReportRendererError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/skills/{skill_id}", status_code=204)
    def delete_skill(
        skill_id: str,
        skills: SkillRegistry = Depends(get_skill_registry),
        store: SQLiteStore = Depends(get_store),
    ) -> Response:
        if any(report.skill_id == skill_id for report in store.list_reports()):
            raise HTTPException(
                status_code=409,
                detail="Skill is used by saved reports and cannot be deleted",
            )
        try:
            skills.delete_user_skill(skill_id)
        except SkillLoadError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(status_code=204)

    @app.get("/api/memory/terms", response_model=list[TerminologyMemory])
    def list_terminology_memory(
        project_id: str | None = Query(default=None),
        store: SQLiteStore = Depends(get_store),
    ) -> list[TerminologyMemory]:
        return store.list_terminology_memory(project_id)

    @app.post("/api/memory/terms", response_model=TerminologyMemory, status_code=201)
    def create_terminology_memory(
        payload: TerminologyMemoryCreate,
        store: SQLiteStore = Depends(get_store),
    ) -> TerminologyMemory:
        try:
            values = payload.model_dump(exclude={"confirmed"})
            return store.create_terminology_memory(**values)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/memory/terms/{memory_id}", status_code=204)
    def delete_terminology_memory(
        memory_id: str,
        store: SQLiteStore = Depends(get_store),
    ) -> Response:
        try:
            store.delete_terminology_memory(memory_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=204)

    return app


app = create_app()
