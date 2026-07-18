# Combined Project Register

Date: 2026-07-17
Classification: internal
System: Edge1 / Big Bird / WW.CX operational tooling

## Purpose

This is the top-level combined register for the Edge1 management interface,
Big Bird private library, handoff/restore materials, AI filesystem connector,
and related connector work.

Use this file first when recovering context, preparing a handoff, or deciding
what remains.

## Current Baseline

| Area | Current State | Evidence |
| --- | --- | --- |
| Edge1 management checkout | Ready | `/opt/edge1-management-interface` |
| GitHub remote | Ready | `git@github.com:johnkaminski727-alt/edge1-management-interface.git` |
| Local bare remote | Ready | `/opt/git/edge1-management-interface.git` |
| Latest autonomous baseline | Ready | `1f37a52 Add autonomous completion project controls` |
| Worktree state | Clean at last verification | `git status --short --branch` |
| Static Private Library Search UI | Ready | `tests/validate_static_ui.py` |
| Search API wrapper | Ready | `tests/validate_private_library_server.py` |
| Live direct private library search | Ready | `mode=live_direct results=5` |
| Private library backup | Ready | Verified `.sqlite3.gz.sha256` manifest |
| Handoff docs | Ready | `docs/handoff/` |
| Autonomous controls | Ready | `docs/autonomous-completion/` |
| AI filesystem connector docs | Ready | `docs/ai-filesystem-write-connector/` |

## Restore Anchors

| Item | Location |
| --- | --- |
| Working repo | `/opt/edge1-management-interface` |
| Local bare remote | `/opt/git/edge1-management-interface.git` |
| GitHub remote | `git@github.com:johnkaminski727-alt/edge1-management-interface.git` |
| Big Bird gateway | `/opt/bigbird-ai-gateway` |
| Private library DB | `/var/lib/bigbird-ai-library/library.sqlite3` |
| Private library backups | `/var/backups/bigbird-ai-library` |
| Search wrapper | `server/private_library_search_server.py` |
| Search runner | `bin/run_private_library_search.sh` |
| Handoff verifier | `tools/handoff/verify_handoff_state.py` |

## Known Private Library Imports

| Stage / Document | Status | Path / ID |
| --- | --- | --- |
| `5e99800b73aaedd3c33967e09d9ef1da` | Committed | `operations/edge1-private-library-update-20260716.md` |
| Edge1 static UI milestone | Committed | `operations/edge1-management-interface-static-ui-implementation-20260716.md` |
| AI filesystem write connector import | Committed | `operations/edge1-ai-filesystem-write-connector-library-import-20260716.md` |
| Edge1 register migration files | Approved/committed during project | `operations` collection |
| Private Library Search realistic build note | Approved/committed during project | `operations` collection |

Confirmed committed record:

```text
stage_id: 5e99800b73aaedd3c33967e09d9ef1da
status: committed
committed_path: operations/edge1-private-library-update-20260716.md
document_id: 7c5007f7e4386b1a1fdc560d63088290
sha256: 78f046720b517e889360a7e4fd9cd6b492b15fe01a0dff13a264961e43a69aaa
```

## Backup Register

Most recent verified private library backup:

```text
/var/backups/bigbird-ai-library/bigbird-ai-library-20260717T030209Z.sqlite3.gz
```

Manifest:

```text
/var/backups/bigbird-ai-library/bigbird-ai-library-20260717T030209Z.sqlite3.gz.sha256
```

SHA-256:

```text
95a05c496b005e0717694b099bdb3081752d3f202c11d7a2d3fe070761478a4e
```

Verification:

```bash
sudo sha256sum -c /var/backups/bigbird-ai-library/bigbird-ai-library-20260717T030209Z.sqlite3.gz.sha256
```

Observed result:

```text
/var/backups/bigbird-ai-library/bigbird-ai-library-20260717T030209Z.sqlite3.gz: OK
```

## Operational Validation Commands

Run from:

```bash
cd /opt/edge1-management-interface
```

Commands:

```bash
python3 tools/handoff/verify_handoff_state.py
python3 tests/validate_static_ui.py
python3 tests/validate_private_library_server.py
git status --short --branch
```

Live direct search check:

```bash
python3 - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location("s", "server/private_library_search_server.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
status, payload = m.search_payload("VPN", "operations", 5)
print(status)
print(payload.get("mode"))
print(len(payload.get("results", [])))
PY
```

Expected:

```text
HTTPStatus.OK
live_direct
5
```

## Related Connector Tracks

| Track | Status | Notes |
| --- | --- | --- |
| AI filesystem write connector | Documented / staged workflow | Operator approval model remains required for writes |
| Google Drive read-only OAuth connector | Separate active project | Keep credentials out of git; scopes limited to Drive read-only/profile/email/openid |
| WW.CX time-card API/audit bridge | Separate active project | API verified for entry update and audit trail |
| Big Bird networking / Spamhaus filtering | Separate pending project | Requires networking-specific validation and likely DNS/service checks |
| Scanned receipt analysis | Separate urgent intake project | Government-program receipt analysis should be handled as its own artifact flow |

## Open Items

| Item | Approval Needed? | Notes |
| --- | --- | --- |
| Turn search wrapper into managed systemd service | Maybe | Localhost-only service is safe; route exposure requires approval. 2026-07-18: unit, installer, smoke test, and runbook prepared (`deploy/`, `registers/private-library-search-service-register-20260718.md`); Edge1 install pending operator |
| Expose UI through private/VPN route | Yes | Public/private route boundary must be approved. 2026-07-18: approval-gated assets prepared (`deploy/nginx/`, `registers/private-library-search-route-register-20260718.md`); nothing active until operator approves and installs on Edge1 |
| Continue Google Drive OAuth connector | Existing separate approval | Do not expand scopes without approval |
| Finish Big Bird networking / Spamhaus project | Likely | May involve DNS/network/firewall changes |
| Build receipt-analysis intake workflow | No for local artifact work | Ask before connecting external accounts or uploading sensitive files |

## Guardrails

- Keep credentials, backups, tokens, private keys, and OAuth secrets out of git.
- Ask before destructive actions.
- Ask before DNS changes.
- Ask before public exposure.
- Ask before billing changes.
- Ask before OAuth publishing or scope expansion.

