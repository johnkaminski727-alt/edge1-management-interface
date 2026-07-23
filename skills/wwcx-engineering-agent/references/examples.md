# Examples

## Continue a deployment repair

User: "Continue and finish the Edge1 deployment."

Behavior:
- inspect branch, status, remote state, service, and fresh logs;
- preserve unrelated work;
- repair source and installer defects;
- validate syntax, tests, service state, and health;
- commit, push, update runbook and `.agent/` state;
- report only after completion or a real approval boundary.

## Maintain a repository

User: "Finish the pending routine work and update the repositories."

Behavior:
- discover pending issues, failing CI, stale docs, and uncommitted changes;
- complete all safe independent work;
- publish focused commits and PRs;
- leave explicit blockers with evidence.

## Self-improve the skill

Trigger: repeated work reveals a missing guard, validation step, or handoff field.

Behavior:
- generalize the lesson;
- update the smallest instruction/reference;
- validate and repackage the entire skill;
- record the change in release notes;
- never broaden permissions or remove safeguards.
