# Report Skill Studio

A local-first, open-source workbench that turns transcripts and notes into reviewed, versioned, Skill-driven reports and PDF artifacts.

The project is currently under active MVP development.

## MVP workflow

1. Paste or import a transcript.
2. Select a declarative report Skill and a user-configured model provider.
3. Generate a structured report draft.
4. Review, edit, validate, and confirm the draft.
5. Render the confirmed report to HTML and PDF.
6. Promote user-confirmed terminology corrections into project memory.

The workbench includes a project-level terminology and spoken-correction table.
Confirmed mappings are applied to later transcripts before model generation.
Validation distinguishes blocking structural errors from non-blocking writing
suggestions, and each issue can be located back to its report field.

## Bundled Skill

The bundled `default-weekly-meeting` Skill uses four fixed sections: overall
conclusion, this week's progress, next week's plan, and risks/coordination.
Project, product, customer, department, and person names may appear only inside
content blocks; they cannot become section headings. The JSON Schema and
deterministic validator both enforce this boundary.

All bundled examples and terminology are synthetic. Runtime data, local `.env`
files, transcripts, generated artifacts, and model credentials are excluded
from Git.

## Repository layout

- `apps/server` — local FastAPI service
- `apps/web` — React workbench
- `packages/skill_engine` — Skill contracts and validation
- `packages/report_renderer` — deterministic HTML/PDF renderer
- `skills/default-weekly-meeting` — bundled weekly meeting Skill
- `docs` — architecture and development notes

## Development

See [docs/development.md](docs/development.md) for local setup, daily startup,
test commands,
environment variables, and optional PDF dependencies. See
[docs/skill-spec.md](docs/skill-spec.md) for the v0.1 declarative Skill contract.

## License

MIT. See [LICENSE](LICENSE).
