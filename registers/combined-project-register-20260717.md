# Combined Project Register

Date: 2026-07-19
Classification: internal
System: Edge1 / Big Bird / WW.CX operational tooling

## Purpose

This is the top-level combined register for the Edge1 management interface,
Big Bird private library, handoff/restore materials, AI filesystem connector,
messaging integration, and related connector work.

Use this file first when recovering context, preparing a handoff, or deciding
what remains.

## Current Baseline

| Area | Current State | Evidence |
| --- | --- | --- |
| Edge1 management checkout | Ready | `/opt/edge1-management-interface` |
| GitHub remote | Ready | `git@github.com:johnkaminski727-alt/edge1-management-interface.git` |
| Local bare remote | Ready | `/opt/git/edge1-management-interface.git` |
| Current merged baseline | Ready | `89329fad Add BigBird messaging gateway adapter` |
| Worktree state | Clean at last verification | `git status --short` returned no entries after telephony restoration |
| Static Private Library Search UI | Ready | `tests/validate_static_ui.py` |
| Search API wrapper | Ready | `tests/validate_private_library_server.py` |
| Live direct private library search | Ready | `mode=live_direct results=5` |
| Private library backup | Ready | Verified `.sqlite3.gz.sha256` manifest |
| Handoff docs | Ready | `docs/handoff/` |
| Autonomous controls | Ready | `docs/autonomous-completion/` and `docs/autonomous-operations/` |
| AI filesystem connector docs | Ready | `docs/ai-filesystem-write-connector/` |
| WW.CX messaging repository layer | Merged | PR #22 and `services/wwcx-messaging-gateway/` |
| BigBird messaging adapter | Merged and staged | PR #23; commit `89329fad21cf55b0cdff08fbe90b053456801d5b`; `/opt/bigbird-ai-gateway/.staging/wwcx-messaging` |
| BigBird messaging live activation | Pending | Read-only `messaging.status.read` activation gate remains |

## Restore Anchors

| Item | Location |
| --- | --- |
| Working repo | `/opt/edge1-management-interface` |
| Local bare remote | `/opt/git/edge1-management-interface.git` |
| GitHub remote | `git@github.com:johnkaminski727-alt/edge1-management-interface.git` |
| Big Bird gateway | `/opt/bigbird-ai-gateway` |
| BigBird messaging staging | `/opt/bigbird-ai-gateway/.staging/wwcx-messaging` |
| BigBird messaging register | `registers/bigbird-messaging-integration-register-20260719.md` |
| BigBird messaging archive handoff | `docs/archive/bigbird-messaging-staged-handoff-20260719.md` |
| Temporary telephony preservation copy | `/opt/edge1-untracked-backup-20260719T173408Z` |
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

Messaging integration preservation state:

- Temporary backup: `/opt/edge1-untracked-backup-20260719T173408Z`
- Preserved telephony content was reported identical to the merged repository content.
- Retain until final read-only messaging activation closeout; it is not the rollback package for the future live BigBird activation.

## BigBird Messaging Integration Status

Repository work:

- Messaging management repository layer merged through PR #22.
- BigBird adapter merged through PR #23.
- PR #23 checks passed before squash merge.
- Merge commit: `89329fad21cf55b0cdff08fbe90b053456801d5b`.

Edge1 staging:

- Adapter staged at `/opt/bigbird-ai-gateway/.staging/wwcx-messaging`.
- Python compilation passed.
- Tool manifest and management contract JSON validation passed.
- Safe default confirmed: `WWCX_MESSAGING_CONTROL_ENABLED=false`.
- No live registry, credentials, service reload, public listening port, customer traffic, or carrier routing changes were made.

Remaining authorized phase:

- Inspect the live BigBird registry and authorization/audit implementation.
- Verify the actual messaging management endpoint.
- Create and install a dedicated read-only credential outside Git.
- Back up affected live BigBird runtime files and configuration.
- Install and register only `messaging.status.read`.
- Perform controlled reload and verify health, authorization rejection, bounded output, audit events, and rollback.

Explicitly out of scope without separate approval:

- `messaging.control.pause`
- `messaging.control.resume`
- Enabling `WWCX_MESSAGING_CONTROL_ENABLED=true`
- Customer/carrier traffic, firewall, DNS, certificate, emergency-calling, or public-exposure changes

Known follow-up:

- `integrations/bigbird-messaging/scripts/install-staged.sh` lacks the executable bit in the merged tree. Invocation through `sh` succeeded. Correct the mode in a focused repository change.

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
python3 -m unittest discover -s integrations/bigbird-messaging/tests -v
python3 -m pytest -q integrations/bigbird_messaging/test_tools.py
python3 -m compileall -q integrations/bigbird_messaging
python3 -m json.tool integrations/bigbird-messaging/tool-manifest.json >/dev/null
python3 -m json.tool integrations/bigbird-messaging/contract/management-api-v1.json >/dev/null
git status --short
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
| BigBird messaging integration | Repository complete / Edge1 staged | Read-only live activation remains; controls disabled |
| Big Bird networking / Spamhaus filtering | Separate pending project | Requires networking-specific validation and likely DNS/service checks |
| Scanned receipt analysis | Separate urgent intake project | Government-program receipt analysis should be handled as its own artifact flow |

## Open Items

| Item | Approval Needed? | Notes |
| --- | --- | --- |
| Activate BigBird messaging status read-only | Authorized within documented boundary | Inspect runtime, create protected read token, register only `messaging.status.read`, reload with rollback, verify audit |
| Enable messaging pause/resume controls | Yes, separate production approval | Must remain disabled |
| Correct staged installer executable bit | No | Focused repository change; currently usable through `sh` |
| Remove temporary telephony backup | Yes, intentional cleanup | Remove only after final messaging activation closeout confirms no recovery dependency |
| Turn search wrapper into managed systemd service | Maybe | Localhost-only service is safe; route exposure requires approval. 2026-07-18: unit, installer, smoke test, and runbook prepared (`deploy/`, `registers/private-library-search-service-register-20260718.md`); Edge1 install pending operator |
| Expose UI through private/VPN route | Yes | Public/private route boundary must be approved |
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
- Keep messaging control disabled until separately approved.
