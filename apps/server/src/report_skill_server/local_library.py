from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .models import LocalLibraryInfo, MarkdownSyncResult, Report, utc_now
from .storage import SQLiteStore


_INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def safe_path_component(value: str, *, fallback: str, max_length: int = 100) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _INVALID_COMPONENT.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    if not normalized or normalized in {".", ".."}:
        normalized = fallback
    if normalized.casefold() in _WINDOWS_RESERVED:
        normalized = f"_{normalized}"
    return normalized[:max_length].rstrip(" .") or fallback


def _yaml_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _quote_lines(text: str) -> list[str]:
    lines = text.splitlines() or [""]
    return [f"> {line}" if line else ">" for line in lines]


def _table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def render_report_markdown(report: Report, project_name: str) -> str:
    content = report.content
    title = str(content.get("title") or report.title)
    meeting_date = str(content.get("meeting_date") or report.updated_at.date().isoformat())
    lines = [
        "---",
        "report_skill_studio: true",
        f"report_id: {_yaml_string(report.id)}",
        f"project: {_yaml_string(project_name)}",
        f"title: {_yaml_string(title)}",
        f"date: {_yaml_string(meeting_date)}",
        f"status: {_yaml_string(report.status.value)}",
        f"skill: {_yaml_string(report.skill_id)}",
        f"updated: {_yaml_string(report.updated_at.isoformat())}",
        "---",
        "",
        f"# {title}",
        "",
    ]

    summary = str(content.get("executive_summary") or "").strip()
    if summary:
        lines.extend(["> [!summary] 执行摘要", *_quote_lines(summary), ""])

    cards = content.get("summary_cards")
    if isinstance(cards, list) and cards:
        lines.extend(["## 概览", "", "| 项目 | 内容 |", "| --- | --- |"])
        for card in cards:
            if not isinstance(card, dict):
                continue
            lines.append(
                f"| {_table_cell(card.get('label', ''))} | {_table_cell(card.get('value', ''))} |"
            )
        lines.append("")

    sections = content.get("sections")
    if not isinstance(sections, list):
        sections = []
    for section_index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        section_title = str(section.get("title") or f"章节 {section_index}")
        lines.extend([f"## {section_index:02d} {section_title}", ""])
        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "paragraph":
                text = str(block.get("text") or "").strip()
                if text:
                    lines.extend([text, ""])
            elif block_type == "bullet_list":
                items = block.get("items")
                if isinstance(items, list):
                    lines.extend([f"- {item}" for item in items if str(item).strip()])
                    lines.append("")
            elif block_type == "project_table":
                columns = block.get("columns")
                rows = block.get("rows")
                if isinstance(columns, list) and columns:
                    lines.append("| " + " | ".join(_table_cell(item) for item in columns) + " |")
                    lines.append("| " + " | ".join("---" for _ in columns) + " |")
                    if isinstance(rows, list):
                        for row in rows:
                            if not isinstance(row, list):
                                continue
                            cells = [*row[: len(columns)], *([""] * max(0, len(columns) - len(row)))]
                            lines.append("| " + " | ".join(_table_cell(item) for item in cells) + " |")
                    lines.append("")
            elif block_type == "status_cards":
                status_cards = block.get("cards")
                if isinstance(status_cards, list):
                    for card in status_cards:
                        if not isinstance(card, dict):
                            continue
                        lines.extend(
                            [
                                f"### {card.get('title', '未命名事项')}",
                                "",
                                f"**状态：** {card.get('status', '未说明')}",
                                "",
                            ]
                        )
                        details = card.get("details")
                        if isinstance(details, list):
                            lines.extend([f"- {detail}" for detail in details if str(detail).strip()])
                            lines.append("")
            elif block_type == "callout":
                tone = str(block.get("tone") or "note")
                callout_type = {
                    "neutral": "note",
                    "info": "info",
                    "success": "success",
                    "warning": "warning",
                    "danger": "danger",
                }.get(tone, "note")
                callout_title = str(block.get("title") or "提示")
                callout_text = str(block.get("text") or "").strip()
                lines.extend(
                    [
                        f"> [!{callout_type}] {callout_title}",
                        *_quote_lines(callout_text),
                        "",
                    ]
                )

    return "\n".join(lines).rstrip() + "\n"


class LocalMarkdownLibrary:
    SETTING_KEY = "local_markdown_library_root"

    def __init__(self, store: SQLiteStore, default_root: Path):
        self.store = store
        self.default_root = default_root

    def _root(self) -> Path:
        stored = self.store.get_setting(self.SETTING_KEY)
        candidate = Path(stored) if stored else self.default_root
        return candidate.expanduser().resolve()

    def info(self) -> LocalLibraryInfo:
        root = self._root()
        exists = root.is_dir()
        probe_parent = root
        while not probe_parent.exists() and probe_parent != probe_parent.parent:
            probe_parent = probe_parent.parent
        writable = os.access(root, os.W_OK) if exists else os.access(probe_parent, os.W_OK)
        return LocalLibraryInfo(
            root_path=str(root),
            configured=self.store.get_setting(self.SETTING_KEY) is not None,
            exists=exists,
            writable=writable,
        )

    def configure(self, root_path: str) -> LocalLibraryInfo:
        candidate = Path(root_path.strip()).expanduser()
        if not candidate.is_absolute():
            raise ValueError("local library path must be an absolute path")
        root = candidate.resolve()
        if root == Path(root.anchor):
            raise ValueError("filesystem root cannot be used as the local library")
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError("local library path is not a directory")
        probe = root / f".report-skill-studio-{uuid4().hex}.tmp"
        try:
            probe.write_text("write test", encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"local library is not writable: {exc}") from exc
        finally:
            probe.unlink(missing_ok=True)
        self.store.set_setting(self.SETTING_KEY, str(root))
        return self.info()

    def status(self, report_id: str) -> MarkdownSyncResult:
        report = self.store.get_report(report_id)
        root = self._root()
        record = self.store.get_report_markdown_file(report_id)
        folder_name = self.store.get_project_markdown_folder(report.project_id)
        if record is None or folder_name is None:
            return self._result("unsynced", root, message="尚未同步到本地 Markdown 项目库。")
        project_directory = (root / folder_name).resolve()
        if not project_directory.is_relative_to(root):
            return self._result(
                "error",
                root,
                message="项目文件夹解析到了项目库之外，已拒绝访问。",
            )
        target = project_directory / record["filename"]
        relative_path = target.relative_to(root)
        if not target.is_file():
            return self._result(
                "missing",
                root,
                target=target,
                relative_path=relative_path,
                message="本地 Markdown 文件已被移动或删除，可重新同步生成。",
            )
        try:
            actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError as exc:
            return self._result(
                "error",
                root,
                target=target,
                relative_path=relative_path,
                message=f"无法读取本地 Markdown：{exc}",
            )
        if actual_hash != record["content_hash"]:
            return self._result(
                "conflict",
                root,
                target=target,
                relative_path=relative_path,
                message="Markdown 已在外部修改，为避免覆盖，自动同步已暂停。",
                synced_at=datetime.fromisoformat(record["synced_at"]),
            )
        return self._result(
            "synced",
            root,
            target=target,
            relative_path=relative_path,
            message="Markdown 已同步到本地项目文件夹。",
            synced_at=datetime.fromisoformat(record["synced_at"]),
        )

    def sync(self, report_id: str) -> MarkdownSyncResult:
        report = self.store.get_report(report_id)
        root = self._root()
        if not report.content:
            return self._result("no_content", root, message="报告尚无内容，暂不生成 Markdown。")
        try:
            root.mkdir(parents=True, exist_ok=True)
            project = self.store.get_project(report.project_id)
            folder_name = self._project_folder(report.project_id, project.name)
            project_directory = root / folder_name
            project_directory.mkdir(parents=True, exist_ok=True)
            project_directory = project_directory.resolve()
            if not project_directory.is_relative_to(root):
                return self._result(
                    "error",
                    root,
                    message="项目文件夹解析到了项目库之外，已拒绝写入。",
                )

            record = self.store.get_report_markdown_file(report.id)
            previous_target = project_directory / record["filename"] if record else None

            if record and previous_target and previous_target.is_file():
                actual_hash = hashlib.sha256(previous_target.read_bytes()).hexdigest()
                if actual_hash != record["content_hash"]:
                    return self._result(
                        "conflict",
                        root,
                        target=previous_target,
                        relative_path=previous_target.relative_to(root),
                        message="Markdown 已在外部修改，为避免覆盖，自动同步已暂停。",
                        synced_at=datetime.fromisoformat(record["synced_at"]),
                    )

            allocated_title = None
            if record:
                allocated_title = self._title_from_allocated_filename(report, record["filename"])
            if allocated_title is None:
                filename, allocated_title = self._report_filename(
                    report,
                    project_directory,
                    ignored_filename=record["filename"] if record else None,
                )
            else:
                filename = record["filename"]

            current_title = str(report.content.get("title") or report.title)
            if report.title != allocated_title or current_title != allocated_title:
                report = self.store.align_report_document_title(report.id, allocated_title)

            target = project_directory / filename
            relative_path = target.relative_to(root)

            markdown = render_report_markdown(report, project.name)
            encoded = markdown.encode("utf-8")
            content_hash = hashlib.sha256(encoded).hexdigest()
            synced_at = utc_now()
            temporary = project_directory / f".{report.id}.{uuid4().hex}.tmp.md"
            try:
                temporary.write_bytes(encoded)
                temporary.chmod(0o600)
                temporary.replace(target)
                if previous_target and previous_target != target:
                    previous_target.unlink(missing_ok=True)
            finally:
                temporary.unlink(missing_ok=True)
            self.store.set_report_markdown_file(
                report.id,
                filename=filename,
                content_hash=content_hash,
                synced_at=synced_at,
            )
            return self._result(
                "synced",
                root,
                target=target,
                relative_path=relative_path,
                message="Markdown 已同步到本地项目文件夹。",
                synced_at=synced_at,
            )
        except OSError as exc:
            return self._result(
                "error",
                root,
                message=f"Markdown 同步失败：{exc}",
            )

    def delete_report_file(self, report_id: str) -> None:
        report = self.store.get_report(report_id)
        targets = self._verified_report_targets([report_id])
        self._delete_verified_targets(targets)
        self._remove_project_directory_if_empty(report.project_id)

    def delete_project_files(self, project_id: str) -> None:
        self.store.get_project(project_id)
        report_ids = [report.id for report in self.store.list_reports(project_id)]
        targets = self._verified_report_targets(report_ids)
        self._delete_verified_targets(targets)
        self._remove_project_directory_if_empty(project_id)

    def _verified_report_targets(self, report_ids: list[str]) -> list[Path]:
        """Preflight every mapped file before any destructive filesystem change."""

        root = self._root()
        targets: list[Path] = []
        for report_id in report_ids:
            report = self.store.get_report(report_id)
            record = self.store.get_report_markdown_file(report_id)
            folder_name = self.store.get_project_markdown_folder(report.project_id)
            if record is None or folder_name is None:
                continue
            target = (root / folder_name / record["filename"]).resolve()
            if not target.is_relative_to(root):
                raise ValueError("Markdown file resolved outside the configured library")
            if not target.exists():
                continue
            if not target.is_file():
                raise ValueError(f"Markdown path is not a file: {record['filename']}")
            try:
                actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError(f"unable to verify Markdown before deletion: {exc}") from exc
            if actual_hash != record["content_hash"]:
                raise ValueError(
                    f"Markdown has external changes and was not deleted: {record['filename']}"
                )
            targets.append(target)
        return targets

    @staticmethod
    def _delete_verified_targets(targets: list[Path]) -> None:
        for target in targets:
            target.unlink(missing_ok=True)

    def _remove_project_directory_if_empty(self, project_id: str) -> None:
        folder_name = self.store.get_project_markdown_folder(project_id)
        if folder_name is None:
            return
        root = self._root()
        project_directory = (root / folder_name).resolve()
        if project_directory.is_relative_to(root) and project_directory.is_dir():
            try:
                project_directory.rmdir()
            except OSError:
                # Preserve non-empty folders and any user-owned files inside them.
                pass

    def _project_folder(self, project_id: str, project_name: str) -> str:
        existing = self.store.get_project_markdown_folder(project_id)
        if existing:
            return existing
        base = safe_path_component(project_name, fallback="未命名项目", max_length=80)
        assigned = {
            name.casefold()
            for owner, name in self.store.list_project_markdown_folders().items()
            if owner != project_id
        }
        candidate = base
        suffix = 2
        while candidate.casefold() in assigned:
            candidate = f"{base}-{suffix}"
            suffix += 1
        self.store.set_project_markdown_folder(project_id, candidate)
        return candidate

    @staticmethod
    def _title_from_allocated_filename(report: Report, filename: str) -> str | None:
        meeting_date = str(report.content.get("meeting_date") or report.updated_at.date().isoformat())
        title = str(report.content.get("title") or report.title)
        base_stem = safe_path_component(
            f"{meeting_date} {title}",
            fallback=report.id,
            max_length=140,
        )
        filename_stem = Path(filename).stem
        if filename_stem == base_stem:
            return title
        match = re.fullmatch(rf"{re.escape(base_stem)}-(\d+)", filename_stem)
        if match and int(match.group(1)) >= 2:
            return f"{title}-{match.group(1)}"
        return None

    @staticmethod
    def _report_filename(
        report: Report,
        project_directory: Path,
        *,
        ignored_filename: str | None = None,
    ) -> tuple[str, str]:
        meeting_date = str(report.content.get("meeting_date") or report.updated_at.date().isoformat())
        title = str(report.content.get("title") or report.title)
        base_stem = safe_path_component(
            f"{meeting_date} {title}",
            fallback=report.id,
            max_length=140,
        )
        candidate = f"{base_stem}.md"
        if candidate == ignored_filename or not (project_directory / candidate).exists():
            return candidate, title

        suffix = 2
        while True:
            suffix_label = f"-{suffix}"
            stem = safe_path_component(
                f"{meeting_date} {title}",
                fallback=report.id,
                max_length=140 - len(suffix_label),
            )
            candidate = f"{stem}{suffix_label}.md"
            if candidate == ignored_filename or not (project_directory / candidate).exists():
                return candidate, f"{title}-{suffix}"
            suffix += 1

    @staticmethod
    def _result(
        status: str,
        root: Path,
        *,
        message: str,
        target: Path | None = None,
        relative_path: Path | None = None,
        synced_at: datetime | None = None,
    ) -> MarkdownSyncResult:
        return MarkdownSyncResult(
            status=status,  # type: ignore[arg-type]
            root_path=str(root),
            relative_path=relative_path.as_posix() if relative_path else None,
            file_path=str(target) if target else None,
            message=message,
            synced_at=synced_at,
        )
