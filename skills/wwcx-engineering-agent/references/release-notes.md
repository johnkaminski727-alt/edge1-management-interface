# Release Notes

## 1.1.1 — 2026-08-15

- Added a failure-handling rule for repository shell helpers whose executable mode is not part of the package contract.
- Prefer explicit `sh path/to/helper.sh` invocation over live-checkout `chmod` workarounds when a POSIX shell helper is source-owned as regular text.
- Require source installer/runbook fixes and regression assertions when execute-bit assumptions cause operational failures.

## 1.1.0 — 2026-07-23

- Added capability preflight for access, authority, repository freshness, and execution-path selection.
- Added explicit Inspect, Develop, and Deploy operating modes.
- Added failure classification, rollback requirements, and terminal-state completion rules.
- Added deterministic `.agent/` project-state validation for required files, headings, placeholders, and likely secrets.
- Strengthened project-scoped authority, protected-branch discipline, evidence handling, secret safety, and bounded self-maintenance.
- Clarified that development, staging, and production evidence must remain distinct.

## 1.0.0 — 2026-07-21

- Established autonomous WW.CX engineering workflow.
- Added authority boundaries and continuation rules.
- Added repository, deployment, Python, and documentation validation checklists.
- Added persistent `.agent/` project-state templates.
- Added formal handoff and completion behavior.
- Added bounded self-maintenance procedure.
