# Combined Register Index

Date: 2026-07-17
Classification: internal

## Purpose

This index points operators to the combined register and the underlying
handoff, restore, validation, and connector registers.

## Top-Level Register

```text
registers/combined-project-register-20260717.md
```

Use this first when restoring context, reviewing current state, or deciding the
next project step.

## Supporting Registers And Docs

| File | Role |
| --- | --- |
| `registers/combined-project-register-20260717.md` | Project-wide combined register |
| `registers/autonomous-completion-register-20260717.md` | Autonomous completion register |
| `registers/handoff-register-20260717.md` | Handoff inventory and open items |
| `docs/autonomous-completion/00-charter.md` | Authorization, scope, definition of done |
| `docs/autonomous-completion/01-guardrails.md` | Safety boundaries and approval gates |
| `docs/autonomous-completion/02-restore-index.md` | Restore locations, backups, and scripts |
| `docs/autonomous-completion/03-acceptance-checklist.md` | Final validation checklist |
| `docs/handoff/20260717-edge1-management-interface-handoff.md` | Human handoff summary |
| `docs/handoff/private-library-search-live-direct.md` | Live direct search bridge details |
| `docs/handoff/private-library-backup-runbook.md` | Backup and manifest verification |
| `docs/ai-filesystem-write-connector/00-index.md` | AI filesystem connector documentation index |

## Restore Reading Order

1. `registers/combined-project-register-20260717.md`
2. `docs/autonomous-completion/02-restore-index.md`
3. `docs/handoff/20260717-edge1-management-interface-handoff.md`
4. `docs/autonomous-completion/03-acceptance-checklist.md`
5. Specific subsystem docs as needed.

## Verification

```bash
cd /opt/edge1-management-interface
python3 tools/handoff/verify_handoff_state.py
```

The verifier should require this index and the combined register.

