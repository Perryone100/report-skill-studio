"""Public renderer exceptions."""


class ReportRendererError(RuntimeError):
    """Base class for deterministic rendering failures."""


class ReportDataError(ReportRendererError):
    """The structured report does not match the renderer contract."""


class TemplateSecurityError(ReportRendererError):
    """A template contains executable or externally loaded content."""


class PdfRenderingUnavailableError(ReportRendererError):
    """Playwright or its local Chromium browser is unavailable."""


class PdfRenderError(ReportRendererError):
    """Chromium failed while producing a PDF."""
