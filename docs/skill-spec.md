# Declarative Skill specification v0.3

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

The v0.3 workbench and renderer support this top-level shape:

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
sections, ordering, tones, terminology, and styling, but v0.3 does not support
adding a new block type without application code. The top-level Schema must
require exactly the canonical editable shape with `additionalProperties: false`.
The loader rejects an incompatible Schema before it can reach the editor.

Template markup uses a static presentation allowlist: `html`, `head`, `meta`,
`title`, `style`, `body`, `main`, `header`, `footer`, `section`, `article`,
`aside`, `nav`, `div`, `span`, `p`, `h1`–`h6`, `table`, `thead`, `tbody`,
`tfoot`, `tr`, `th`, `td`, `ul`, `ol`, `li`, `br`, `hr`, `time`, `strong`,
`em`, and `small`. Resource attributes, inline event handlers, inline `style`
attributes, and active meta directives are rejected. The renderer injects its
own Content Security Policy into standalone HTML.

## ZIP installation

The workbench can install one Skill from a `.zip` file. The archive may either
contain the Skill files at its root or wrap them in one directory, but it must
contain exactly one `skill.yaml`. Skill IDs use lowercase kebab-case. Bundled
IDs are reserved, and replacing an existing user Skill requires the explicit
replacement option.

Installation validates the manifest, every referenced file, JSON Schema,
terminology and validation YAML, renderer compatibility, and HTML/CSS template
safety before atomically moving the Skill into `data/skills/<skill-id>`. Archives
larger than 8 MB, expanding beyond 25 MB, containing more than 200 files, or
containing traversal paths, links, encryption, active script elements, event
handlers, or external template resources are rejected. Skills remain declarative and are never imported as
Python or JavaScript.

## Validation and review

Validation runs after generation, after editing, and before confirmation.
Schema-invalid output cannot enter the editor because the UI cannot interpret
it safely. Structurally valid output with validation findings is saved as a
draft so the user can review it. Error-severity findings block confirmation;
warning and info findings remain visible but do not block confirmation or PDF
export. Only a confirmed report can be exported to PDF.

`required_sections` enforces section IDs, titles, and non-empty content. Set
`allow_additional_sections: false` when a Skill uses a fixed report outline;
duplicate IDs, renamed required sections, and unexpected sections then produce
deterministic validation errors. The bundled Skill uses this mode so project
names stay inside content blocks instead of becoming headings.

Bundled terminology and user-confirmed project memory are merged in one pass.
Project memory wins over global memory, and user memory wins over bundled terms.
Unconfirmed candidate corrections never affect generation or validation. The
workbench exposes project memory as an editable source-to-canonical correction
table; re-saving the same source updates the existing rule, and the confirmed
mapping is applied before the next model call.

## Template safety

The renderer escapes all report data. Templates may not load remote or local
resources, execute scripts, register event handlers, or use active CSS such as
imports and URLs. PDF layout is deterministic HTML/CSS rendered with Chromium.
