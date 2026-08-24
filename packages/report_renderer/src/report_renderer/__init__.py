"""Safe, deterministic structured report rendering."""

from .errors import (
    PdfRenderError,
    PdfRenderingUnavailableError,
    ReportDataError,
    ReportRendererError,
    TemplateSecurityError,
)
from .renderer import render_html, render_pdf

__all__ = [
    "PdfRenderError",
    "PdfRenderingUnavailableError",
    "ReportDataError",
    "ReportRendererError",
    "TemplateSecurityError",
    "render_html",
    "render_pdf",
]
