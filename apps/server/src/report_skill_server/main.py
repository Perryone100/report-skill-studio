from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from report_renderer import PdfRenderingUnavailableError, ReportRendererError
from skill_engine import SkillLoadError

from . import __version__
from .config import get_settings
from .models import (
    GenerateReportRequest,
    HealthResponse,
    Job,
    Project,
    ProjectCreate,
    ProviderInfo,
    Report,
    ReportCreate,
    ReportUpdate,
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
    settings = get_settings()
    providers = [MockChatProvider()]
    if (
        settings.openai_compatible_base_url
        and settings.openai_compatible_api_key
        and settings.openai_compatible_model
    ):
        providers.append(
            OpenAICompatibleChatProvider(
                base_url=settings.openai_compatible_base_url,
                api_key=settings.openai_compatible_api_key.get_secret_value(),
                model=settings.openai_compatible_model,
            )
        )
    return ProviderRegistry(providers)


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry(get_settings().skills_dir)


def get_generation_service(
    store: SQLiteStore = Depends(get_store),
    providers: ProviderRegistry = Depends(get_provider_registry),
    skills: SkillRegistry = Depends(get_skill_registry),
) -> ReportGenerationService:
    return ReportGenerationService(store, providers, skills, get_settings().artifacts_dir)


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
                filename=artifact.name,
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PdfRenderingUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
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
