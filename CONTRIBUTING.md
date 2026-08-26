# Contributing

Thanks for helping improve Report Skill Studio.

## Development workflow

1. Create a focused branch from `main`.
2. Install dependencies using the frozen lockfiles described in [docs/development.md](docs/development.md).
3. Keep changes within the package boundaries in [docs/architecture.md](docs/architecture.md).
4. Add tests for every public behavior and use only synthetic fixtures.
5. Run `uv run --frozen pytest`, `pnpm test:web`, and `pnpm build:web`.
6. Open a pull request describing user impact, verification, privacy implications, and any compatibility change.

Do not commit `.env`, API keys, databases, transcripts, reports, model files, generated archives, or screenshots containing personal information. New Skill examples must be fictional and declarative. Cross-package API changes should remain additive until all consumers are migrated.

Security vulnerabilities belong in the [private reporting channel](SECURITY.md), not a public issue.
