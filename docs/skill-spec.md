# Declarative Skill specification v0.1

A report Skill controls writing instructions, the structured report contract,
terminology, deterministic validation, and presentation. A Skill is data only:
the loader never imports or executes Python or JavaScript from the directory.

## Directory contract

```text
my-skill/
├── skill.yaml
├── instructions.md
├── prompts/generate.md
├── schemas/report.schema.json
├── memory/default-terms.yaml
├── validators/rules.yaml
└── templates/
    ├── report.html
    └── report.css
```

`skill.yaml` may reference different safe relative filenames. References may not
be absolute, escape the Skill directory, or point to a missing file.

## Generation variables

The application expands these variables in `prompts/generate.md` before calling
the selected provider:

- `{{report_date}}`
- `{{project_memory}}`
- `{{confirmed_terminology}}`
- `{{transcript}}`

`instructions.md` is sent as the model's writing policy. The prompt and JSON
Schema are sent with the user input. Provider output must be a JSON object.

## Canonical report contract

The v0.1 workbench and renderer support this top-level shape:

```text
title
meeting_date
executive_summary
summary_cards[]
sections[]
  id
  title
  blocks[]
```

Supported block types are `paragraph`, `bullet_list`, `project_table`,
`status_cards`, and `callout`. Skills may choose sections, titles, required
sections, ordering, tones, terminology, and styling, but v0.1 does not support
adding a new block type without application code. A Skill that uses the bundled
renderer must keep its JSON Schema compatible with this canonical contract.

## Validation and review

Validation runs after generation, after editing, and before confirmation.
Schema-invalid output cannot enter the editor because the UI cannot interpret
it safely. Structurally valid output with terminology, required-section, or
forbidden-phrase issues is saved as a draft so the user can repair it. Only a
valid draft can be confirmed; only a confirmed report can be exported to PDF.

`required_sections` enforces section IDs, titles, and non-empty content. Set
`allow_additional_sections: false` when a Skill uses a fixed report outline;
duplicate IDs, renamed required sections, and unexpected sections then produce
deterministic validation errors. The bundled Skill uses this mode so project
names stay inside content blocks instead of becoming headings.

Bundled terminology and user-confirmed project memory are merged in one pass.
Project memory wins over global memory, and user memory wins over bundled terms.
Unconfirmed candidate corrections never affect generation or validation.

## Template safety

The renderer escapes all report data. Templates may not load remote or local
resources, execute scripts, register event handlers, or use active CSS such as
imports and URLs. PDF layout is deterministic HTML/CSS rendered with Chromium.
