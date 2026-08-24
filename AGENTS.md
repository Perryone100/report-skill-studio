# Engineering coordination

This repository is a local-first, Skill-driven report workbench.

## Architecture boundaries

- `apps/server/`: FastAPI composition root, HTTP API, persistence, jobs, provider adapters.
- `apps/web/`: React/TypeScript user interface. Do not edit from backend tasks.
- `packages/skill_engine/`: Skill manifest, loading, schemas, terminology, validation.
- `packages/report_renderer/`: HTML/PDF rendering and renderer tests.
- `skills/default-weekly-meeting/`: bundled reference Skill. Template files are owned by the renderer task; all other files are owned by the Skill task.
- `docs/`: architecture decisions and user/developer documentation, coordinated by the root task.

Avoid editing another task's owned directory. Cross-package API changes should be additive until integration.

## Product constraints

- Local-first: no source audio, transcripts, reports, or secrets leave the machine unless the user explicitly selects a cloud provider.
- BYOK: provider credentials must never be committed, logged, or stored as plaintext in SQLite.
- Skills are declarative and may not execute arbitrary Python or JavaScript.
- Model output is structured data; models do not author final PDF layout directly.
- Every correction promoted to long-term memory must be user-confirmed.

## Quality

- Add tests with each public behavior.
- Keep fixtures synthetic or explicitly approved for repository use.
- Run the narrowest relevant test suite before handing off.
