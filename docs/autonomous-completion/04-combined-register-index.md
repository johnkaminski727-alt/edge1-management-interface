# Combined Register Index

Date: 2026-07-19
Classification: internal

## Purpose

This index points operators to the combined register and the underlying
handoff, restore, validation, connector, operational-smoke-test, and archive
records.

## Top-Level Register

```text
registers/combined-project-register-20260719.md
```

Use this first when restoring broad project context. The prior
`registers/combined-project-register-20260717.md` remains a retained historical
baseline.

## Supporting Registers And Docs

| File | Role |
| --- | --- |
| `registers/combined-project-register-20260719.md` | Current project-wide combined register and archive-preparation source of truth |
| `registers/combined-project-register-20260717.md` | Superseded historical baseline |
| `registers/edge1-authenticated-smoke-test-register-20260719.md` | Authenticated Edge1 checks, corrective actions, residual warnings, and archive boundary |
| `docs/archive/edge1-authenticated-smoke-test-closeout-20260719.md` | Sanitized closeout; raw host evidence intentionally excluded |
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

## Edge1 Smoke-Test Archive Boundary

The durable repository record is limited to the sanitized combined register,
smoke-test register, and closeout document. Do not import or commit the
host-local directory `/tmp/edge1-readonly-smoke-20260719T182823Z`, because the
temporary evidence wrapper failed its synthetic bearer-value redaction test.

Operational corrections recorded as completed and verified:

- incomplete default Fail2ban `sshd` jail disabled through a local override;
- `fail2ban.service` enabled and active with seven verified jails;
- Fail2ban chains observed through the `iptables-nft` backend;
- `logrotate.service` completed successfully;
- zero failed systemd units observed after correction.

Residual follow-up remains in the current combined register and smoke-test
register, including persistent redaction tooling, elevated swap trending,
messaging activation, MariaDB VPN scope review, Edge1 checkout reconciliation,
and approved private-library import of the sanitized records.

## Restore Reading Order

1. `registers/combined-project-register-20260719.md`
2. `registers/edge1-authenticated-smoke-test-register-20260719.md`
3. `docs/archive/edge1-authenticated-smoke-test-closeout-20260719.md`
4. `docs/autonomous-completion/02-restore-index.md`
5. `docs/handoff/20260717-edge1-management-interface-handoff.md`
6. `docs/autonomous-completion/03-acceptance-checklist.md`
7. Current GitHub history and a fresh host inspection when current state matters.

## Verification

```bash
cd /opt/edge1-management-interface
python3 tools/handoff/verify_handoff_state.py
```

The verifier should require this index and the current combined register. The
smoke-test register and archive closeout are supplemental timestamped records;
they do not replace a fresh production-state verification.