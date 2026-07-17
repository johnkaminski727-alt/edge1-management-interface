# Edge1 Restore And Handoff Index

Date: 2026-07-17
Classification: internal

## Git Repositories

| Purpose | Location |
| --- | --- |
| Working checkout | `/opt/edge1-management-interface` |
| Local bare remote | `/opt/git/edge1-management-interface.git` |
| GitHub remote | `git@github.com:johnkaminski727-alt/edge1-management-interface.git` |

## Critical Handoff Files

| File | Purpose |
| --- | --- |
| `docs/handoff/20260717-edge1-management-interface-handoff.md` | Main handoff summary |
| `docs/handoff/private-library-search-live-direct.md` | Live direct search bridge documentation |
| `docs/handoff/private-library-backup-runbook.md` | Private library backup and restore handling |
| `registers/handoff-register-20260717.md` | Handoff inventory and open items |
| `registers/autonomous-completion-register-20260717.md` | Master autonomous project register |
| `docs/autonomous-completion/00-charter.md` | Scope, authorization, definition of done |
| `docs/autonomous-completion/01-guardrails.md` | Approval and safety boundaries |
| `docs/autonomous-completion/03-acceptance-checklist.md` | Final acceptance checks |

## Critical Scripts

| Script | Purpose |
| --- | --- |
| `bin/run_private_library_search.sh` | Run localhost UI/API wrapper |
| `server/private_library_search_server.py` | Search API wrapper and direct library bridge |
| `tests/validate_static_ui.py` | Static UI validation |
| `tests/validate_private_library_server.py` | Search wrapper validation |
| `tools/handoff/create_private_library_backup.sh` | Consistent compressed private library backup |
| `tools/handoff/verify_handoff_state.py` | Read-only handoff state verifier |

## Private Backup Location

Private library backups are outside git:

```text
/var/backups/bigbird-ai-library
```

Most recent known backup at handoff time:

```text
/var/backups/bigbird-ai-library/bigbird-ai-library-20260717T030209Z.sqlite3.gz
```

Known SHA-256:

```text
95a05c496b005e0717694b099bdb3081752d3f202c11d7a2d3fe070761478a4e
```

## Restore Outline

1. Restore or clone `/opt/edge1-management-interface`.
2. Confirm git remotes and latest commit.
3. Restore Big Bird private library database from verified backup if needed.
4. Restore ACLs allowing the wrapper process read/traverse access to the library DB path.
5. Run validation scripts.
6. Start localhost wrapper.
7. Confirm `/api/private-library/search` returns `mode: live_direct`.

