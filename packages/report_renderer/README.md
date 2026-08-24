# Report renderer

This package turns a validated structured report into deterministic HTML. PDF
output is optional and uses Playwright's local Chromium browser.

```python
from pathlib import Path

from report_renderer import render_html, render_pdf

html = render_html(report, Path("skills/default-weekly-meeting/templates"))
render_pdf(
    report,
    Path("skills/default-weekly-meeting/templates"),
    Path("output/report.pdf"),
)
```

The template contract is deliberately small: `report.html` must contain exactly
one each of `{{DOCUMENT_TITLE}}`, `{{REPORT_CSS}}`, and `{{REPORT_CONTENT}}`.
Templates cannot contain scripts, executable HTML, links, imports, or resource
URLs. All report values are escaped before insertion.

Install PDF support and its browser separately:

```shell
pip install -e 'packages/report_renderer[pdf]'
playwright install chromium
```
