"""Structured report to HTML/PDF rendering.

Templates are intentionally presentation-only. They expose three fixed string
slots and cannot execute code or retrieve resources. Every model/user supplied
value is converted to plain text and HTML escaped here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
import re
from typing import Any

from .errors import (
    PdfRenderError,
    PdfRenderingUnavailableError,
    ReportDataError,
    TemplateSecurityError,
)

_DOCUMENT_TITLE = "{{DOCUMENT_TITLE}}"
_REPORT_CSS = "{{REPORT_CSS}}"
_REPORT_CONTENT = "{{REPORT_CONTENT}}"

_UNSAFE_HTML_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"<\s*(?:script|iframe|object|embed|svg|math|form|img|video|audio|source|track|picture|link|base|canvas)\b",
            re.I,
        ),
        "executable or resource-loading HTML",
    ),
    (re.compile(r"\son[a-z]+\s*=", re.I), "inline event handler"),
    (
        re.compile(
            r"\b(?:src|srcset|href|xlink:href|poster|background|action|formaction|style)\s*=",
            re.I,
        ),
        "external or local resource reference",
    ),
    (re.compile(r"javascript\s*:", re.I), "javascript URL"),
    (re.compile(r"<\s*meta\b[^>]*http-equiv\s*=", re.I), "active meta directive"),
)

_UNSAFE_CSS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"@import\b", re.I), "CSS import"),
    (re.compile(r"@font-face\b", re.I), "external font declaration"),
    (re.compile(r"url\s*\(", re.I), "CSS resource URL"),
    (re.compile(r"(?:image-set|-webkit-image-set)\s*\(", re.I), "CSS image resource"),
    (re.compile(r"expression\s*\(", re.I), "CSS expression"),
    (re.compile(r"javascript\s*:", re.I), "javascript URL"),
    (re.compile(r"https?\s*://|(?<!:)//", re.I), "remote resource URL"),
)

_SAFE_TONES = {"neutral", "info", "success", "warning", "danger"}
_STATUS_TONES = {
    "已完成": "success",
    "完成": "success",
    "正常": "success",
    "进行中": "info",
    "推进中": "info",
    "计划中": "neutral",
    "待关注": "warning",
    "风险": "danger",
    "阻塞": "danger",
}


def render_html(
    report: Mapping[str, Any],
    template_directory: str | Path,
    *,
    html_filename: str = "report.html",
    css_filename: str = "report.css",
) -> str:
    """Render *report* with a safe declarative template directory.

    The report contract matches the bundled Skill schema: ``title``,
    ``meeting_date``, ``executive_summary``, ``summary_cards``, and ``sections``.
    Block types are paragraph, bullet_list, project_table, status_cards, and
    callout. Unknown blocks fail closed instead of being interpreted as HTML.
    """

    if not isinstance(report, Mapping):
        raise ReportDataError("report must be an object")

    template_dir = Path(template_directory).resolve()
    html_path = _resolve_template_file(template_dir, html_filename)
    css_path = _resolve_template_file(template_dir, css_filename)
    try:
        template = html_path.read_text(encoding="utf-8")
        css = css_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReportDataError(
            f"template directory must contain report.html and report.css: {template_dir}"
        ) from exc

    _validate_template(template, css)

    title = _required_text(report, "title", "report")
    body = _render_report(report)
    result = template.replace(_DOCUMENT_TITLE, _html_text(title))
    result = result.replace(_REPORT_CSS, css)
    result = result.replace(_REPORT_CONTENT, body)
    if re.search(r"{{[A-Z0-9_]+}}", result):
        raise TemplateSecurityError("template contains an unsupported placeholder")
    return result


def render_pdf(
    report: Mapping[str, Any],
    template_directory: str | Path,
    output_path: str | Path,
    *,
    chromium_executable: str | Path | None = None,
    html_filename: str = "report.html",
    css_filename: str = "report.css",
) -> Path:
    """Render an A4 PDF with a local Playwright Chromium browser.

    PDF support is optional. Missing Python/browser dependencies produce a
    targeted error with install commands rather than a raw import or launch
    traceback.
    """

    destination = Path(output_path)
    if destination.suffix.lower() != ".pdf":
        raise ReportDataError("PDF output path must end with .pdf")

    html = render_html(
        report,
        template_directory,
        html_filename=html_filename,
        css_filename=css_filename,
    )
    sync_playwright, playwright_error = _load_sync_playwright()
    destination.parent.mkdir(parents=True, exist_ok=True)

    browser = None
    try:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {"headless": True}
            if chromium_executable is not None:
                launch_options["executable_path"] = str(chromium_executable)
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=str(destination),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            browser.close()
            browser = None
    except playwright_error as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "executable doesn't exist" in message.lower():
            raise PdfRenderingUnavailableError(
                "Playwright Chromium is not installed. Run: playwright install chromium"
            ) from exc
        raise PdfRenderError(f"Chromium could not render the PDF: {message}") from exc
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass

    if not destination.is_file() or destination.stat().st_size == 0:
        raise PdfRenderError("Chromium completed without creating a non-empty PDF")
    return destination


def _resolve_template_file(root: Path, relative_name: str) -> Path:
    candidate = (root / relative_name).resolve()
    if not candidate.is_relative_to(root):
        raise TemplateSecurityError(f"template file escapes its directory: {relative_name}")
    return candidate


def _load_sync_playwright() -> tuple[Any, type[Exception]]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PdfRenderingUnavailableError(
            "PDF support requires Playwright. Install it with "
            "`pip install -e 'packages/report_renderer[pdf]'`, then run "
            "`playwright install chromium`."
        ) from exc
    return sync_playwright, PlaywrightError


def _validate_template(template: str, css: str) -> None:
    for placeholder in (_DOCUMENT_TITLE, _REPORT_CSS, _REPORT_CONTENT):
        if template.count(placeholder) != 1:
            raise TemplateSecurityError(
                f"report.html must contain exactly one {placeholder} placeholder"
            )
    for pattern, label in _UNSAFE_HTML_PATTERNS:
        if pattern.search(template):
            raise TemplateSecurityError(f"report.html contains forbidden {label}")
    for pattern, label in _UNSAFE_CSS_PATTERNS:
        if pattern.search(template):
            raise TemplateSecurityError(f"report.html contains forbidden {label}")
        if pattern.search(css):
            raise TemplateSecurityError(f"report.css contains forbidden {label}")
    known_placeholders_removed = template
    for placeholder in (_DOCUMENT_TITLE, _REPORT_CSS, _REPORT_CONTENT):
        known_placeholders_removed = known_placeholders_removed.replace(placeholder, "")
    if "{{" in known_placeholders_removed or "}}" in known_placeholders_removed:
        raise TemplateSecurityError("report.html contains an unsupported placeholder")


def _render_report(report: Mapping[str, Any]) -> str:
    title = _required_text(report, "title", "report")
    meeting_date = _required_text(report, "meeting_date", "report")
    executive_summary = _required_text(report, "executive_summary", "report")
    summary_cards = _required_sequence(report, "summary_cards", "report")
    sections = _required_sequence(report, "sections", "report")

    parts = [
        '<main class="report">',
        '<header class="report-header">',
        '<div class="report-kicker">WEEKLY MEETING REPORT</div>',
        f'<h1>{_html_text(title)}</h1>',
        '<div class="report-meta">',
        f'<span class="date-label">会议日期</span><time>{_html_text(meeting_date)}</time>',
        "</div>",
        "</header>",
    ]

    if summary_cards:
        parts.append('<section class="summary-grid" aria-label="本周概览">')
        for index, raw_card in enumerate(summary_cards):
            card = _mapping(raw_card, f"summary_cards[{index}]")
            label = _required_text(card, "label", f"summary_cards[{index}]")
            value = _required_text(card, "value", f"summary_cards[{index}]")
            tone = _tone(card.get("tone"))
            parts.extend(
                (
                    f'<article class="summary-card tone-{tone}">',
                    f'<div class="summary-label">{_html_text(label)}</div>',
                    f'<div class="summary-value">{_html_text(value)}</div>',
                    "</article>",
                )
            )
        parts.append("</section>")

    parts.extend(
        (
            '<section class="executive-summary report-section">',
            '<div class="section-heading"><span class="section-index">00</span>',
            '<h2>执行摘要</h2></div>',
            f'<div class="executive-summary-body">{_html_text(executive_summary)}</div>',
            "</section>",
        )
    )

    for section_index, raw_section in enumerate(sections, start=1):
        section = _mapping(raw_section, f"sections[{section_index - 1}]")
        section_id = _required_text(section, "id", f"sections[{section_index - 1}]")
        section_title = _required_text(section, "title", f"sections[{section_index - 1}]")
        blocks = _required_sequence(section, "blocks", f"sections[{section_index - 1}]")
        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", section_id).strip("-") or f"section-{section_index}"
        parts.extend(
            (
                f'<section class="report-section" id="{escape(safe_id, quote=True)}">',
                '<div class="section-heading">',
                f'<span class="section-index">{section_index:02d}</span>',
                f'<h2>{_html_text(section_title)}</h2>',
                "</div>",
            )
        )
        for block_index, raw_block in enumerate(blocks):
            block = _mapping(raw_block, f"{section_id}.blocks[{block_index}]")
            parts.append(_render_block(block, f"{section_id}.blocks[{block_index}]"))
        parts.append("</section>")

    parts.extend(
        (
            '<footer class="page-footer">',
            f'<span>{_html_text(title)}</span><span>{_html_text(meeting_date)}</span>',
            "</footer>",
            "</main>",
        )
    )
    return "".join(parts)


def _render_block(block: Mapping[str, Any], path: str) -> str:
    block_type = _required_text(block, "type", path)
    if block_type == "paragraph":
        return f'<div class="content-block paragraph-block"><p>{_html_text(_required_text(block, "text", path))}</p></div>'

    if block_type == "bullet_list":
        items = _required_sequence(block, "items", path)
        rendered = "".join(
            f"<li>{_html_text(_as_text(item, f'{path}.items[{index}]'))}</li>"
            for index, item in enumerate(items)
        )
        return f'<div class="content-block list-block"><ul>{rendered}</ul></div>'

    if block_type == "project_table":
        columns = _required_sequence(block, "columns", path)
        rows = _required_sequence(block, "rows", path)
        column_texts = [_as_text(value, f"{path}.columns[{index}]") for index, value in enumerate(columns)]
        if not column_texts:
            raise ReportDataError(f"{path}.columns must not be empty")
        head = "".join(f"<th>{_html_text(value)}</th>" for value in column_texts)
        rendered_rows: list[str] = []
        for row_index, raw_row in enumerate(rows):
            row = _sequence(raw_row, f"{path}.rows[{row_index}]")
            if len(row) != len(column_texts):
                raise ReportDataError(
                    f"{path}.rows[{row_index}] has {len(row)} cells; expected {len(column_texts)}"
                )
            cells = "".join(
                f"<td>{_html_text(_as_text(value, f'{path}.rows[{row_index}][{cell_index}]'))}</td>"
                for cell_index, value in enumerate(row)
            )
            rendered_rows.append(f"<tr>{cells}</tr>")
        return (
            '<div class="content-block table-block"><table>'
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(rendered_rows)}</tbody>"
            "</table></div>"
        )

    if block_type == "status_cards":
        cards = _required_sequence(block, "cards", path)
        rendered_cards = []
        for index, raw_card in enumerate(cards):
            card_path = f"{path}.cards[{index}]"
            card = _mapping(raw_card, card_path)
            title = _required_text(card, "title", card_path)
            status = _required_text(card, "status", card_path)
            details = card.get("details", [])
            detail_values = _sequence(details, f"{card_path}.details")
            detail_html = "".join(
                f"<li>{_html_text(_as_text(detail, f'{card_path}.details[{detail_index}]'))}</li>"
                for detail_index, detail in enumerate(detail_values)
            )
            tone = _tone(card.get("tone"), status=status)
            details_markup = f"<ul>{detail_html}</ul>" if detail_html else ""
            rendered_cards.append(
                f'<article class="status-card tone-{tone}">'
                f'<div class="status-card-head"><h3>{_html_text(title)}</h3>'
                f'<span class="status-badge">{_html_text(status)}</span></div>'
                f"{details_markup}</article>"
            )
        return f'<div class="content-block status-grid">{"".join(rendered_cards)}</div>'

    if block_type == "callout":
        title = block.get("title")
        title_markup = ""
        if title is not None:
            title_markup = f"<h3>{_html_text(_as_text(title, f'{path}.title'))}</h3>"
        text = _required_text(block, "text", path)
        tone = _tone(block.get("tone"))
        return (
            f'<aside class="content-block callout tone-{tone}">'
            f"{title_markup}<p>{_html_text(text)}</p></aside>"
        )

    raise ReportDataError(f"{path}.type has unsupported value: {block_type!r}")


def _html_text(value: str) -> str:
    return escape(_clean_display_text(value), quote=True).replace("\n", "<br>")


def _clean_display_text(value: str) -> str:
    # The renderer must preserve user-confirmed business content. Writing-policy
    # suggestions belong to Skill validation; silently deleting phrases here can
    # corrupt legitimate descriptions such as “AI 生成能力”.
    return re.sub(r"[ \t]{2,}", " ", value).strip(" \t·|/-")


def _tone(value: Any, *, status: str | None = None) -> str:
    if isinstance(value, str) and value in _SAFE_TONES:
        return value
    if status:
        return _STATUS_TONES.get(status, "neutral")
    return "neutral"


def _required_text(value: Mapping[str, Any], key: str, path: str) -> str:
    if key not in value:
        raise ReportDataError(f"{path}.{key} is required")
    return _as_text(value[key], f"{path}.{key}")


def _as_text(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ReportDataError(f"{path} must be a string")
    return value


def _required_sequence(value: Mapping[str, Any], key: str, path: str) -> Sequence[Any]:
    if key not in value:
        raise ReportDataError(f"{path}.{key} is required")
    return _sequence(value[key], f"{path}.{key}")


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ReportDataError(f"{path} must be an array")
    return value


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReportDataError(f"{path} must be an object")
    return value
