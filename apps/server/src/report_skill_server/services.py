from __future__ import annotations

import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import uuid4

from report_renderer import ReportRendererError, render_html, render_pdf
from skill_engine import (
    LoadedSkill,
    SkillLoadError,
    TermEntry,
    Terminology,
    TerminologyLayer,
    load_skill,
    normalize_transcript,
)

from .local_library import LocalMarkdownLibrary, safe_path_component
from .models import Job, JobStatus, ProviderInfo, Report, SkillInfo
from .providers import ChatProvider, ProviderGenerationError
from .storage import SQLiteStore


class ProviderRegistry:
    def __init__(self, providers: list[ChatProvider]):
        self._providers = {provider.id: provider for provider in providers}
        if len(self._providers) != len(providers):
            raise ValueError("provider ids must be unique")

    def get(self, provider_id: str) -> ChatProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise LookupError(f"provider not found or not configured: {provider_id}") from exc

    def list(self) -> list[ProviderInfo]:
        return [
            ProviderInfo(
                id=provider.id,
                name=provider.name,
                model=provider.model,
                local=provider.local,
                configured=True,
            )
            for provider in self._providers.values()
        ]


class SkillRegistry:
    MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
    MAX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
    MAX_FILES = 200

    def __init__(self, skills_dir: Path, user_skills_dir: Path | None = None):
        self.skills_dir = skills_dir.resolve()
        self.user_skills_dir = user_skills_dir.resolve() if user_skills_dir else None

    @staticmethod
    def _validate_skill_id(skill_id: str) -> str:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_id):
            raise SkillLoadError("skill id must be a lowercase kebab-case identifier")
        return skill_id

    def _bundled_directory(self, skill_id: str) -> Path:
        return self.skills_dir / self._validate_skill_id(skill_id)

    def _user_directory(self, skill_id: str) -> Path | None:
        if self.user_skills_dir is None:
            return None
        return self.user_skills_dir / self._validate_skill_id(skill_id)

    def get(self, skill_id: str) -> LoadedSkill:
        bundled = self._bundled_directory(skill_id)
        user = self._user_directory(skill_id)
        directory = bundled if bundled.is_dir() else user
        if directory is None or not directory.is_dir():
            raise SkillLoadError(f"Skill not found: {skill_id}")
        skill = load_skill(directory)
        if skill.manifest.id != skill_id:
            raise SkillLoadError(
                f"skill directory {skill_id!r} contains manifest id {skill.manifest.id!r}"
            )
        return skill

    def list(self) -> list[SkillInfo]:
        skills: list[SkillInfo] = []
        seen: set[str] = set()
        catalogs = [(self.skills_dir, "bundled")]
        if self.user_skills_dir is not None:
            catalogs.append((self.user_skills_dir, "user"))
        for catalog, source in catalogs:
            if not catalog.is_dir():
                continue
            for directory in sorted(catalog.iterdir()):
                if (
                    directory.name.startswith(".")
                    or not directory.is_dir()
                    or not (directory / "skill.yaml").is_file()
                ):
                    continue
                skill = load_skill(directory)
                if skill.manifest.id in seen:
                    raise SkillLoadError(
                        f"duplicate Skill id across catalogs: {skill.manifest.id}"
                    )
                seen.add(skill.manifest.id)
                skills.append(self._skill_info(skill, source=source))
        return skills

    def install_archive(
        self,
        archive: bytes,
        *,
        replace_existing: bool = False,
        protected_skill_ids: set[str] | None = None,
    ) -> SkillInfo:
        if self.user_skills_dir is None:
            raise SkillLoadError("user Skill installation is not configured")
        if not archive:
            raise SkillLoadError("Skill ZIP is empty")
        if len(archive) > self.MAX_ARCHIVE_BYTES:
            raise SkillLoadError("Skill ZIP exceeds the 8 MB upload limit")

        self.user_skills_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="skill-upload-") as temporary:
            extraction_root = Path(temporary)
            self._extract_archive(archive, extraction_root)
            manifests = list(extraction_root.rglob("skill.yaml"))
            if len(manifests) != 1:
                raise SkillLoadError("Skill ZIP must contain exactly one skill.yaml")
            candidate = load_skill(manifests[0].parent)
            self._validate_templates(candidate)

            skill_id = candidate.manifest.id
            bundled = self._bundled_directory(skill_id)
            if bundled.exists():
                raise SkillLoadError(f"bundled Skill cannot be replaced: {skill_id}")
            destination = self._user_directory(skill_id)
            assert destination is not None
            if destination.exists() and not replace_existing:
                raise FileExistsError(
                    f"Skill {skill_id} is already installed; enable replacement to update it"
                )
            if (
                destination.exists()
                and replace_existing
                and skill_id in (protected_skill_ids or set())
            ):
                raise ValueError(
                    f"Skill {skill_id} is used by saved reports and cannot be replaced"
                )

            staging = self.user_skills_dir / f".{skill_id}.{uuid4().hex}.tmp"
            backup = self.user_skills_dir / f".{skill_id}.{uuid4().hex}.backup"
            shutil.copytree(candidate.root, staging)
            installed_candidate = load_skill(staging)
            self._validate_templates(installed_candidate)
            try:
                if destination.exists():
                    destination.rename(backup)
                staging.rename(destination)
            except Exception:
                if backup.exists() and not destination.exists():
                    backup.rename(destination)
                raise
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
                if backup.exists():
                    shutil.rmtree(backup)

        return self._skill_info(load_skill(destination), source="user")

    def delete_user_skill(self, skill_id: str) -> None:
        if self._bundled_directory(skill_id).is_dir():
            raise ValueError("bundled Skills cannot be deleted")
        directory = self._user_directory(skill_id)
        if directory is None or not directory.is_dir():
            raise SkillLoadError(f"installed Skill not found: {skill_id}")
        shutil.rmtree(directory)

    def _extract_archive(self, archive: bytes, target: Path) -> None:
        from io import BytesIO

        try:
            bundle = zipfile.ZipFile(BytesIO(archive))
        except zipfile.BadZipFile as exc:
            raise SkillLoadError("uploaded file is not a valid ZIP archive") from exc
        with bundle:
            members = bundle.infolist()
            files = [member for member in members if not member.is_dir()]
            if len(files) > self.MAX_FILES:
                raise SkillLoadError("Skill ZIP contains too many files")
            if sum(member.file_size for member in files) > self.MAX_UNCOMPRESSED_BYTES:
                raise SkillLoadError("Skill ZIP expands beyond the 25 MB safety limit")
            for member in members:
                name = member.filename
                path = Path(name)
                mode = member.external_attr >> 16
                if (
                    not name
                    or "\\" in name
                    or ":" in name
                    or path.is_absolute()
                    or ".." in path.parts
                    or stat.S_ISLNK(mode)
                    or member.flag_bits & 0x1
                ):
                    raise SkillLoadError(f"unsafe ZIP entry: {name!r}")
                if member.is_dir():
                    continue
                destination = target.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)

    @staticmethod
    def _validate_templates(skill: LoadedSkill) -> None:
        templates = skill.manifest.files.templates
        if templates is None:
            raise SkillLoadError("installed Skill must define HTML and CSS templates")
        preview = {
            "title": "Skill 安装检查",
            "meeting_date": "2026-01-01",
            "executive_summary": "用于验证模板安全性的本地合成内容。",
            "summary_cards": [{"label": "状态", "value": "检查中"}],
            "sections": [
                {
                    "id": "preview",
                    "title": "模板预览",
                    "blocks": [
                        {"type": "paragraph", "text": "合成段落"},
                        {"type": "bullet_list", "items": ["合成列表"]},
                        {
                            "type": "project_table",
                            "columns": ["工作项", "进展", "状态", "下一步"],
                            "rows": [["示例", "完成", "已完成", "无"]],
                        },
                        {
                            "type": "status_cards",
                            "cards": [{"title": "示例", "status": "已完成"}],
                        },
                        {"type": "callout", "title": "提示", "text": "合成提示"},
                    ],
                }
            ],
        }
        try:
            render_html(
                preview,
                skill.root,
                html_filename=templates.html,
                css_filename=templates.css,
            )
        except ReportRendererError as exc:
            raise SkillLoadError(f"unsafe or invalid Skill templates: {exc}") from exc

    @staticmethod
    def _skill_info(skill: LoadedSkill, *, source: str) -> SkillInfo:
        return SkillInfo(
            id=skill.manifest.id,
            name=skill.manifest.name,
            version=skill.manifest.version,
            description=skill.manifest.description,
            locale=skill.manifest.locale,
            source=source,
            can_delete=source == "user",
        )


class ReportGenerationService:
    def __init__(
        self,
        store: SQLiteStore,
        providers: ProviderRegistry,
        skills: SkillRegistry,
        artifacts_dir: Path,
        local_library: LocalMarkdownLibrary,
    ):
        self.store = store
        self.providers = providers
        self.skills = skills
        self.artifacts_dir = artifacts_dir
        self.local_library = local_library

    def generate(self, report_id: str, provider_id: str) -> Job:
        report = self.store.get_report(report_id)
        job = self.store.create_job(
            "report_generation",
            {"report_id": report_id, "provider_id": provider_id, "skill_id": report.skill_id},
        )
        self.store.update_job(job.id, status=JobStatus.RUNNING, progress=10)

        try:
            provider = self.providers.get(provider_id)
            skill = self.skills.get(report.skill_id)
            terminology = self._terminology_for_project(skill, report.project_id)
            normalized = normalize_transcript(report.transcript, terminology)
            effective_skill = replace(skill, terminology=terminology)
            content = provider.generate(
                transcript=normalized.text,
                title=report.title,
                instructions=skill.instructions,
                prompt=self._render_prompt(
                    skill,
                    report.project_id,
                    normalized.text,
                    terminology,
                ),
                schema=skill.report_schema,
            )
            validation = effective_skill.validate(content)
            schema_issues = [
                issue for issue in validation.issues if issue.code == "schema.invalid"
            ]
            if schema_issues:
                messages = "; ".join(issue.message for issue in schema_issues[:5])
                raise ProviderGenerationError(
                    f"generated report has an unusable structure: {messages}"
                )
            updated = self.store.update_report(
                report_id,
                content=content,
                reason=f"generated:{provider_id}",
            )
            markdown_sync = self.local_library.sync(updated.id)
            return self.store.update_job(
                job.id,
                status=JobStatus.SUCCEEDED,
                progress=100,
                result={
                    "report_id": updated.id,
                    "version": updated.version,
                    "corrections": [
                        correction.model_dump(mode="json")
                        for correction in normalized.corrections
                    ],
                    "validation": {
                        "valid": validation.valid,
                        "issues": [
                            issue.model_dump(mode="json")
                            for issue in validation.issues
                        ],
                    },
                    "markdown": markdown_sync.model_dump(mode="json"),
                },
            )
        except Exception as exc:
            self.store.update_job(
                job.id,
                status=JobStatus.FAILED,
                progress=100,
                error=str(exc),
            )
            if isinstance(exc, (LookupError, ProviderGenerationError, ValueError)):
                raise
            raise ProviderGenerationError(str(exc)) from exc

    def validate(self, report_id: str) -> dict[str, object]:
        report = self.store.get_report(report_id)
        skill = self.skills.get(report.skill_id)
        terminology = self._terminology_for_project(skill, report.project_id)
        result = replace(skill, terminology=terminology).validate(report.content)
        return {
            "valid": result.valid,
            "issues": [issue.model_dump(mode="json") for issue in result.issues],
        }

    def confirm(self, report_id: str) -> Report:
        validation = self.validate(report_id)
        if not validation["valid"]:
            raise ValueError("report has validation errors and cannot be confirmed")
        self.store.confirm_report(report_id)
        self.local_library.sync(report_id)
        return self.store.get_report(report_id)

    def preview_html(self, report_id: str) -> str:
        report = self.store.get_report(report_id)
        validation = self.validate(report_id)
        if not validation["valid"]:
            raise ValueError("report has validation errors and cannot be previewed")
        skill = self.skills.get(report.skill_id)
        template_root, html_filename, css_filename = self._template_files(skill)
        return render_html(
            report.content,
            template_root,
            html_filename=html_filename,
            css_filename=css_filename,
        )

    def export_pdf(self, report_id: str) -> Path:
        report = self.store.get_report(report_id)
        if report.status.value != "confirmed":
            raise ValueError("report must be confirmed before PDF export")
        skill = self.skills.get(report.skill_id)
        template_root, html_filename, css_filename = self._template_files(skill)
        output_path = self.artifacts_dir / f"{report.id}-v{report.version}.pdf"
        return render_pdf(
            report.content,
            template_root,
            output_path,
            html_filename=html_filename,
            css_filename=css_filename,
        )

    def export_html(self, report_id: str) -> tuple[str, str]:
        report = self.store.get_report(report_id)
        if report.status.value != "confirmed":
            raise ValueError("report must be confirmed before HTML export")
        skill = self.skills.get(report.skill_id)
        template_root, html_filename, css_filename = self._template_files(skill)
        html = render_html(
            report.content,
            template_root,
            html_filename=html_filename,
            css_filename=css_filename,
        )
        return html, self.download_filename(report, "html")

    @staticmethod
    def download_filename(report: Report, extension: str) -> str:
        meeting_date = str(report.content.get("meeting_date") or report.updated_at.date().isoformat())
        title = str(report.content.get("title") or report.title)
        stem = safe_path_component(f"{meeting_date} {title}", fallback=report.id, max_length=140)
        return f"{stem}.{extension}"

    def download_filename_for(self, report_id: str, extension: str) -> str:
        return self.download_filename(self.store.get_report(report_id), extension)

    @staticmethod
    def _template_files(skill: LoadedSkill) -> tuple[Path, str, str]:
        templates = skill.manifest.files.templates
        if templates is None:
            raise ReportRendererError("selected Skill does not define report templates")
        return skill.root, templates.html, templates.css

    def _terminology_for_project(
        self,
        skill: LoadedSkill,
        project_id: str,
    ) -> Terminology:
        """Merge user-confirmed memory over bundled terms in one normalization pass."""

        memories = sorted(
            self.store.list_terminology_memory(project_id),
            key=lambda memory: (memory.project_id is not None, memory.updated_at),
            reverse=True,
        )
        if not memories:
            return skill.terminology

        custom_terms: list[TermEntry] = []
        claimed_variants: set[str] = set()
        for memory in memories:
            variant_key = memory.source_value.casefold()
            if variant_key in claimed_variants:
                continue
            claimed_variants.add(variant_key)
            custom_terms.append(
                TermEntry(
                    canonical=memory.normalized_value,
                    variants=[memory.source_value],
                    layer=(
                        TerminologyLayer.PROJECT
                        if memory.project_id is not None
                        else TerminologyLayer.FIXED
                    ),
                    confirmed=True,
                    note="用户确认的术语记忆",
                )
            )

        bundled_terms: list[TermEntry] = []
        for term in skill.terminology.terms:
            if term.canonical.casefold() in claimed_variants:
                continue
            remaining_variants = [
                variant
                for variant in term.variants
                if variant.casefold() not in claimed_variants
            ]
            if remaining_variants:
                bundled_terms.append(term.model_copy(update={"variants": remaining_variants}))

        return Terminology(
            schema_version=skill.terminology.schema_version,
            terms=[*custom_terms, *bundled_terms],
        )

    def _render_prompt(
        self,
        skill: LoadedSkill,
        project_id: str,
        transcript: str,
        terminology: Terminology,
    ) -> str:
        project = self.store.get_project(project_id)
        project_memory = project.name
        if project.description.strip():
            project_memory += f"\n{project.description.strip()}"

        normalized_transcript = transcript.casefold()
        confirmed_terms = [
            f"{', '.join(term.variants)} → {term.canonical}"
            for term in terminology.terms
            if term.confirmed
            and (
                term.canonical.casefold() in normalized_transcript
                or any(
                    variant.casefold() in normalized_transcript
                    for variant in term.variants
                )
            )
        ]
        replacements = {
            "{{report_date}}": date.today().isoformat(),
            "{{project_memory}}": project_memory,
            "{{confirmed_terminology}}": "\n".join(confirmed_terms),
            "{{transcript}}": transcript,
        }
        prompt = skill.prompt
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt


def ensure_editable(report: Report) -> None:
    if report.status.value != "draft":
        raise ValueError("confirmed reports are immutable")
