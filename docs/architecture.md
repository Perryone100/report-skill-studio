# MVP architecture

Report Skill Studio uses a ports-and-adapters architecture so model vendors, transcription engines, persistence, and rendering remain replaceable.

## Critical path

`source -> transcript -> Skill + memory -> structured draft -> validation -> review -> confirmed report -> renderer -> artifact`

## Package contracts

- The Skill engine loads a declarative Skill directory and returns typed instructions, report schema, terminology, validation rules, and template metadata.
- The application service asks a chat provider for JSON conforming to the selected Skill schema.
- Validation is deterministic and runs before and after user review.
- The renderer accepts only validated structured report data and a trusted declarative template.
- Long-running generation, transcription, and rendering operations use persisted jobs with explicit status.

## Model boundary and cost control

The writing model is used only for semantic extraction, consolidation, and
structured drafting. Transcript terminology normalization, applying a
confirmed correction to the current draft, validation, review state, and
HTML/PDF rendering remain deterministic local operations and do not trigger
another model request.

Before generation, project terminology is applied locally. The model prompt
then includes only terminology entries relevant to the current normalized
transcript rather than the project's entire accumulated memory. The complete
Skill JSON Schema is still sent for output reliability, but it is serialized
without whitespace. These reductions do not remove source facts or writing
rules.

One OpenAI-compatible connection may register multiple writing model ids. This
lets the user choose an economy or higher-quality model per report without
coupling model choice to Skills, storage, validation, or rendering.

## MVP non-goals

- Realtime transcription
- Speaker diarization
- Cloud collaboration or synchronization
- Remote Skill execution
- Automatic Feishu account integration
