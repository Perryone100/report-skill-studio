from __future__ import annotations

from pathlib import Path
import re

import pytest

import report_renderer.renderer as renderer_module
from report_renderer import (
    PdfRenderingUnavailableError,
    ReportDataError,
    TemplateSecurityError,
    render_html,
    render_pdf,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = REPO_ROOT / "skills" / "default-weekly-meeting" / "templates"


@pytest.fixture
def report() -> dict:
    return {
        "title": "产品研发周会纪要",
        "meeting_date": "2026-08-21",
        "executive_summary": "核心项目按计划推进，重点关注上线窗口与资源协同。",
        "summary_cards": [
            {"label": "本周阶段", "value": "重点需求进入联调", "tone": "info"},
            {"label": "核心进展", "value": "功能模块 A 完成验收", "tone": "success"},
            {"label": "重点风险", "value": "测试资源存在冲突", "tone": "warning"},
        ],
        "sections": [
            {
                "id": "this_week_progress",
                "title": "本周工作进展",
                "blocks": [
                    {
                        "type": "project_table",
                        "columns": ["工作项", "进展", "下一步"],
                        "rows": [["功能模块 A", "联调完成", "安排 UAT"]],
                    },
                    {
                        "type": "status_cards",
                        "cards": [
                            {
                                "title": "功能模块 B",
                                "status": "进行中",
                                "details": ["OCR 链路已验证", "等待业务验收"],
                            }
                        ],
                    },
                ],
            },
            {
                "id": "next-week",
                "title": "下周重点计划",
                "blocks": [{"type": "bullet_list", "items": ["完成 UAT", "确认上线窗口"]}],
            },
            {
                "id": "risks",
                "title": "风险与待协调事项",
                "blocks": [
                    {
                        "type": "callout",
                        "title": "资源风险",
                        "text": "测试排期与其他项目重叠。",
                        "tone": "warning",
                    }
                ],
            },
            {
                "id": "followups",
                "title": "关键决策与待办",
                "blocks": [{"type": "paragraph", "text": "请协调测试资源。"}],
            },
        ],
    }


def test_renders_required_business_modules(report: dict) -> None:
    html = render_html(report, TEMPLATE_DIR)

    assert "产品研发周会纪要" in html
    assert "本周整体结论" in html
    assert "重点需求进入联调" in html
    assert "<table>" in html
    assert "本周工作进展" in html
    assert "下周重点计划" in html
    assert "风险与待协调事项" in html
    assert "关键决策与待办" in html
    assert "break-inside: avoid" in html
    assert "size: A4 portrait" in html


def test_escapes_all_dynamic_content(report: dict) -> None:
    report["title"] = '<script>alert("title")</script>'
    report["sections"][0]["blocks"][0]["rows"][0][0] = '<img src=x onerror="alert(1)">'

    html = render_html(report, TEMPLATE_DIR)

    assert "&lt;script&gt;alert(&quot;title&quot;)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html
    assert not re.search(r"<script\b", html, re.I)
    assert not re.search(r"<img\b", html, re.I)


def test_removes_internal_labels_from_display(report: dict) -> None:
    report["title"] += " 图文结合版"
    report["executive_summary"] += " AI生成"
    report["sections"][1]["blocks"][0]["items"].append("内容来源")

    html = render_html(report, TEMPLATE_DIR)

    for label in ("图文结合版", "AI生成", "内容来源"):
        assert label not in html


@pytest.mark.parametrize(
    ("unsafe_html", "unsafe_css"),
    [
        ("<script>alert(1)</script>", ""),
        ('<img src="https://example.test/a.png">', ""),
        ('<img srcset="asset.png 1x, asset-2x.png 2x">', ""),
        ('<div onclick="alert(1)">x</div>', ""),
        ('<div style="background-image: url(asset.png)">x</div>', ""),
        ("", "@import 'evil.css';"),
        ("", "body { background: url(https://example.test/a.png); }"),
    ],
)
def test_rejects_scripts_and_resource_loading(
    tmp_path: Path, report: dict, unsafe_html: str, unsafe_css: str
) -> None:
    (tmp_path / "report.html").write_text(
        "<html><head><title>{{DOCUMENT_TITLE}}</title>"
        f"{unsafe_html}<style>{{{{REPORT_CSS}}}}</style></head>"
        "<body>{{REPORT_CONTENT}}</body></html>",
        encoding="utf-8",
    )
    (tmp_path / "report.css").write_text(f"body {{ color: black; }}{unsafe_css}", encoding="utf-8")

    with pytest.raises(TemplateSecurityError):
        render_html(report, tmp_path)


def test_rejects_unknown_block_instead_of_interpreting_it(report: dict) -> None:
    report["sections"][0]["blocks"] = [{"type": "raw_html", "html": "<b>unsafe</b>"}]

    with pytest.raises(ReportDataError, match="unsupported value"):
        render_html(report, TEMPLATE_DIR)


def test_pdf_dependency_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, report: dict
) -> None:
    def unavailable() -> tuple[object, type[Exception]]:
        raise PdfRenderingUnavailableError(
            "PDF support requires Playwright; run playwright install chromium"
        )

    monkeypatch.setattr(renderer_module, "_load_sync_playwright", unavailable)

    with pytest.raises(PdfRenderingUnavailableError, match="playwright install chromium"):
        render_pdf(report, TEMPLATE_DIR, tmp_path / "report.pdf")


def test_missing_chromium_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, report: dict
) -> None:
    class FakePlaywrightError(Exception):
        pass

    class FakeChromium:
        def launch(self, **_: object) -> None:
            raise FakePlaywrightError("BrowserType.launch: Executable doesn't exist")

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeManager:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(
        renderer_module,
        "_load_sync_playwright",
        lambda: (lambda: FakeManager(), FakePlaywrightError),
    )

    with pytest.raises(PdfRenderingUnavailableError, match="playwright install chromium"):
        render_pdf(report, TEMPLATE_DIR, tmp_path / "report.pdf")


def test_pdf_output_requires_pdf_extension(report: dict, tmp_path: Path) -> None:
    with pytest.raises(ReportDataError, match="end with .pdf"):
        render_pdf(report, TEMPLATE_DIR, tmp_path / "report.html")


def test_custom_template_filenames_are_supported(report: dict, tmp_path: Path) -> None:
    (tmp_path / "layout.tpl").write_text(
        (TEMPLATE_DIR / "report.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "theme.print.css").write_text(
        (TEMPLATE_DIR / "report.css").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    html = render_html(
        report,
        tmp_path,
        html_filename="layout.tpl",
        css_filename="theme.print.css",
    )

    assert report["title"] in html
