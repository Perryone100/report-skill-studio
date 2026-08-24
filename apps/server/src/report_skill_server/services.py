from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

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

from .models import Job, JobStatus, ProviderInfo, Report, SkillInfo
from .providers import ChatProvider, ProviderGenerationError
from .storage import SQLiteStore


class ProviderRegistry:
    def __init__(self, providers: list[ChatProvider]):
        self._providers = {provider.id: provider for provider in providers}

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
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir

    def get(self, skill_id: str) -> LoadedSkill:
        skill = load_skill(self.skills_dir / skill_id)
        if skill.manifest.id != skill_id:
            raise SkillLoadError(
                f"skill directory {skill_id!r} contains manifest id {skill.manifest.id!r}"
            )
        return skill

    def list(self) -> list[SkillInfo]:
        if not self.skills_dir.is_dir():
            return []
        skills: list[SkillInfo] = []
        for directory in sorted(self.skills_dir.iterdir()):
            if not directory.is_dir() or not (directory / "skill.yaml").is_file():
                continue
            skill = load_skill(directory)
            skills.append(
                SkillInfo(
                    id=skill.manifest.id,
                    name=skill.manifest.name,
                    version=skill.manifest.version,
                    description=skill.manifest.description,
                    locale=skill.manifest.locale,
                )
            )
        return skills


class ReportGenerationService:
    def __init__(
        self,
        store: SQLiteStore,
        providers: ProviderRegistry,
        skills: SkillRegistry,
        artifacts_dir: Path,
    ):
        self.store = store
        self.providers = providers
        self.skills = skills
        self.artifacts_dir = artifacts_dir

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
        return self.store.confirm_report(report_id)

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

        confirmed_terms = [
            f"{', '.join(term.variants)} → {term.canonical}"
            for term in terminology.terms
            if term.confirmed
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
