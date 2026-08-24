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

## MVP non-goals

- Realtime transcription
- Speaker diarization
- Cloud collaboration or synchronization
- Remote Skill execution
- Automatic Feishu account integration
