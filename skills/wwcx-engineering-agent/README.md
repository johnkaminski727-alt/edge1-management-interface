# WW.CX Engineering Agent

Installable ChatGPT Skill source for autonomous WW.CX engineering work.

## Package contents

- `SKILL.md` — required skill entrypoint and trigger description
- `agents/openai.yaml` — ChatGPT UI metadata
- `references/workflow.md` — detailed execution lifecycle
- `references/authority.md` — approval and safety boundaries
- `references/validation.md` — completion checklists
- `references/project-state.md` — persistent `.agent/` templates
- `references/handoff-template.md` — durable continuation format
- `references/examples.md` — realistic invocation patterns
- `references/release-notes.md` — version history

## Release

Version 1.0.0 was validated and packaged with the OpenAI skill-creator validator and packager on 2026-07-21.

## Design principle

Proceed autonomously through all safe and reversible work, publish validated changes, maintain durable project state, and stop only at explicit privileged, irreversible, financial, legal, regulatory, credential, or production-traffic boundaries.
