# BigBird Messaging Integration Register

Date: 2026-07-19
Classification: internal
System: Edge1 / BigBird / WW.CX Messaging
Status: repository complete; Edge1 adapter staged; live read-only activation pending

## Objective

Provide BigBird with a least-privileged, auditable interface to the WW.CX messaging management service without exposing provider credentials, message content, database access, or arbitrary HTTP operations.

## Repository baseline

- Repository: `johnkaminski727-alt/edge1-management-interface`
- Edge1 checkout: `/opt/edge1-management-interface`
- Merged baseline: `89329fad21cf55b0cdff08fbe90b053456801d5b`
- Pull request #22: messaging management API repository layer
- Pull request #23: BigBird messaging gateway adapter
- PR #23 merge method: squash
- PR #23 checks: `BigBird Messaging Adapter` and `Validate repository` passed before merge

## Implemented repository components

- `services/wwcx-messaging-gateway/`
- `integrations/bigbird_messaging/`
- `integrations/bigbird-messaging/tool-manifest.json`
- `integrations/bigbird-messaging/contract/management-api-v1.json`
- `integrations/bigbird-messaging/config/bigbird-messaging.env.example`
- `integrations/bigbird-messaging/scripts/install-staged.sh`
- `.github/workflows/bigbird-messaging-adapter.yml`
- `.github/workflows/wwcx-messaging-gateway.yml`

## Edge1 runtime evidence

BigBird gateway:

- Root: `/opt/bigbird-ai-gateway`
- Application directory: `/opt/bigbird-ai-gateway/app`
- Virtual environment: `/opt/bigbird-ai-gateway/venv-v0.3.1-alpha.1`
- Service: `bigbird-ai-gateway.service`
- Service user/group: `bigbird-ai:bigbird-ai`
- Environment file: `/etc/bigbird-ai-gateway.env`
- Bound address: `127.0.0.1:8787`
- Confirmed endpoints: `/v1/health`, `/v1/tools`, `/openapi.json`

Adapter staging:

- Staged location: `/opt/bigbird-ai-gateway/.staging/wwcx-messaging`
- Source JSON validation: passed
- Staged JSON validation: passed
- Python compilation: passed
- Safe default verification: `WWCX_MESSAGING_CONTROL_ENABLED=false`
- Live registry changes: not performed
- Live credential changes: not performed
- Service restart/reload: not performed
- Customer or carrier traffic changes: none

## Authorized next phase

Activate read-only status integration only:

- Tool: `messaging.status.read`
- Scope: `messaging.status.read`
- Operation: `GET /v1/management/status`

The live activation must preserve existing BigBird signing, nonce, authorization, scope, audit, and result-bounding controls.

## Explicitly disabled

Do not enable without a separate production approval:

- `messaging.control.pause`
- `messaging.control.resume`
- `WWCX_MESSAGING_CONTROL_ENABLED=true`
- Generic or arbitrary HTTP access
- Provider, carrier, database, message-body, or recipient-list access

## Remaining deployment gates

1. Inspect the live BigBird registry, dispatcher, authorization, and audit conventions.
2. Verify the actual WW.CX messaging management service address and health.
3. Generate and install a dedicated read-only credential outside Git.
4. Back up affected BigBird files and protected environment configuration.
5. Install the staged adapter into the verified live import path.
6. Register only `messaging.status.read`.
7. Run offline imports, configuration validation, and secret scanning.
8. Perform a controlled BigBird service reload.
9. Verify health, tool listing, authorization rejection, status output, audit records, and rollback.
10. Update this register from `staged` to `read-only live` only after direct runtime verification.

## Rollback and preservation

- Temporary telephony preservation copy: `/opt/edge1-untracked-backup-20260719T173408Z`
- Preserved telephony content was compared with the merged repository and reported identical.
- The backup may be removed only after the final live integration closeout confirms no recovery dependency remains.
- The live activation must create its own timestamped BigBird rollback directory before changing runtime files.

## Known follow-up defect

`integrations/bigbird-messaging/scripts/install-staged.sh` is stored with non-executable mode in the merged repository. It was successfully invoked through `sh`. Correct the executable bit in a focused repository change; this does not block staging or read-only activation.

## Source of truth

Use this register together with:

- `integrations/bigbird-messaging/README.md`
- `services/wwcx-messaging-gateway/docs/bigbird-integration.md`
- `docs/archive/bigbird-messaging-staged-handoff-20260719.md`
- `registers/combined-project-register-20260717.md`
