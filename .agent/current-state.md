# Current State

Last reconciled: 2026-08-20  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`

This file is the concise cross-workstream continuation point. Historical details remain in dated acceptance/runbook records.

## Repository / runtime reconciliation

Repository `main` has advanced normally through Business159 work and is currently `234d00194cf7ef4abb6bdd466c7d9a6f1996fd99`.

The accepted Edge1 Operator and Operations API production runtime remains intentionally pinned to immutable detached worktrees at:

```text
d326d4546abefa695a293266342a5c1075f010e2
```

Live Operator `edge1.git_state` reports that detached runtime revision. The host snapshot independently reports the shared engineering checkout clean on `main` at `234d00194cf7ef4abb6bdd466c7d9a6f1996fd99`, matching `origin/main`.

Do not treat this intentional immutable-runtime/main separation as Git drift.

## Public Edge1 front door

The 2026-08-19 front-door cutover remains **LIVE / ACCEPTED / REVERIFIED** and must not be reopened without fresh contrary evidence.

Accepted ordinary routing remains:

- raw/default IPv4 HTTP `/` -> `302 https://ww.cx/time/`;
- unmatched Host HTTP `/` -> same;
- `edge1.ww.cx` HTTP `/` -> existing `301 https://edge1.ww.cx/`;
- `edge1.ww.cx` HTTPS `/` and `/index.html` -> `302 https://ww.cx/time/`;
- `/edge1-status/` preserved;
- unknown/non-root paths preserved;
- raw HTTPS behavior not weakened;
- PBX/SIP named-host behavior preserved.

Rollback evidence:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh
```

HTTP 302 is intentional. Any 308 promotion is optional future work.

## Global systemd trust boundary

Status: **LIVE / REPAIRED / VERIFIED**.

Accepted state remains:

```text
/etc/systemd/system owner=root:root mode=0755
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/systemd-unit-dir-boundary/20260820T011819Z
```

The historical Time Authority installer defect that caused the directory ownership drift is corrected in source. Future privileged changes under `/etc/systemd/system` remain separately approval-gated.

## Edge1 Operator / Secure MCP Tunnel / ChatGPT

Status: **LIVE / ACCEPTED / PERSISTENT / WORKSPACE PUBLISHED**.

Authoritative closeout records:

- `docs/edge1-operator/17-post-deployment-acceptance-20260820.md`;
- `docs/edge1-operator/18-workspace-publication-acceptance-20260820.md`;
- `docs/edge1-operator/13-completion-status.md`.

Accepted production properties:

- `edge1-operator-mcp.service` active/enabled;
- `edge1-secure-mcp-tunnel.service` active/enabled;
- `bigbird-ai-tunnel.service` active;
- principal `edge1-operator`;
- MCP loopback listener `127.0.0.1:8102`;
- Operations API loopback listener `127.0.0.1:8097`;
- Operations API healthy with 27 fixed actions and `mutations_enabled=false`;
- exactly 16 public Edge1 tools;
- public tools are read-only, non-destructive, closed-world/local and idempotent;
- no generic execution/write tool is exposed;
- internal `agent.turn.*` capabilities are excluded from public dispatch;
- persistent turn state is stored under `/var/lib/edge1-operator-mcp/turn-state` without weakening `ProtectSystem=strict`.

Fresh 2026-08-20 connector verification from this ChatGPT runtime succeeded for:

- `edge1.identity`;
- `edge1.health`;
- `edge1.network_state`;
- `edge1.asterisk_status`;
- `edge1.bigbird_status`;
- inventory/services/configuration diagnostics.

Asterisk native diagnostics now succeed through the bounded Asterisk-owned fixed snapshot mechanism. Do not widen `wwadmin` or Operator access to the general Asterisk control socket.

The old tunnel-client OAuth-metadata doctor compatibility finding is historical commissioning context, not an active activation blocker. Do not add synthetic OAuth endpoints or replace the shared tunnel client solely to make the old raw doctor green.

## Adjacent service health

Fresh live service inspection shows Apache, Asterisk, Kamailio, Edge1 Operator, Operations API, Edge1 Secure MCP Tunnel, Big Bird gateway/tunnel, telephony, messaging, timekeeping, network sensor, and related core services active.

Two known Big Bird connector lifecycle units remain failed and are intentionally not disturbed by unrelated work:

- `bigbird-edge1-connector-maintenance.service`;
- `bigbird-edge1-connector.service`.

Big Bird itself reports healthy, enabled, read-only mode with library integrity `ok`.

## Control Surfaces

Bounded summary/listener inventory remains available. Current listener classification reports 37 internal-service, 4 private-control, and 22 `unknown-needs-attribution` listeners. These are provenance/attribution follow-up items, not justification for firewall, DNS, SIP, SSH, or listener changes by themselves.

Asterisk diagnostics are no longer limited to passive fallback: the accepted Asterisk-owned fixed snapshot path is working and reports native CLI status `ok`.

The executable `scripts/control-surfaces-live-inventory.sh` packaging issue was corrected previously. A final retained execution manifest/summary remains a useful housekeeping task if not already preserved in a later evidence record.

Existing FreePBX Admin/UCP private-source boundaries remain unchanged. Any future native-session broker remains separately gated.

## Security-boundary inventory

The read-only inventory aggregate remains:

```text
records=164
mapped=160
missing_known=0
unknown_preserved=4
filesystem_anomaly=1
```

The source-controlled fail-closed classifier for the residual artifact set is merged. Durable closeout still needs the exact protected evidence directory plus metadata/hash/path classification of the four preserved unknowns and one reviewed filesystem anomaly if that live classification has not yet been retained.

DNS, firewall, certificates, authentication policy, listeners, and production traffic remain separately gated.

## Business159 / WW.CX public deployment

The Business159 website deployment path remains **LIVE / ACCEPTED** under the release-owned synchronization model. Do not revert to whole-document-root `rsync --delete`.

Accepted public release remains:

```text
commit=01ee93cf0337006c5d44031a5f9eb1a83e1d0100
release=/home/wwcxjywl/releases/ww-cx-website/20260819T201010Z
backup=/home/wwcxjywl/shared/ww-cx-website/backups/public-html-20260819T201010Z.tar.gz
```

The Business159 persistent tunnel/plugin work has advanced in repository `main`. Fresh Edge1 service inspection shows `business159-secure-mcp-tunnel.service` active. Treat connector-level Business159 read-only/staged-filesystem acceptance as separate until verified through the dedicated Business159 app/runtime; do not infer raw-shell or deployment authority from service activity.

## Asterisk / alerting

Asterisk is active and current bounded native diagnostics report status `ok`. Historical warning follow-up established configured PJSIP transport, loopback UDP `127.0.0.1:5061`, boot persistence, loopback HTTPS/WSS, local TLS success, and zero audit failures.

No listener/firewall/certificate/SIP/startup-policy mutation is justified from these findings. The offline CAP-CP/EBS laboratory remains isolated; no `Actual` alert delivery, calls/pages, tones, or public delivery path are authorized.

## DTMF provider work

Externally blocked. Last retained mailbox state from 2026-08-19 found no substantive provider technical answer after the 2026-08-14 notice that there was still no update.

```text
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

No live calls or DTMF transmission without separate explicit authorization.

## Current continuation order

1. Keep the accepted Edge1 public front door, Operator publication/runtime boundary, and Business159 release-owned deployment model unchanged.
2. Reconcile and retain the five residual security-boundary inventory classifications plus exact evidence directory if still missing.
3. Retain a final Control Surfaces executable-inventory manifest/summary and corrected Asterisk audit record if not already captured elsewhere.
4. Continue Business159 connector-level read-only/staged-filesystem acceptance through the dedicated Business159 runtime; keep raw shell and deployment apply disabled unless separately authorized.
5. Attribute remaining `unknown-needs-attribution` listeners through read-only provenance work before considering any exposure change.
6. Leave DTMF provider work pending until a substantive external response arrives.

## Safety boundary

No credentials or secret values in Git/chat/evidence. No public MCP proxy. No new WAN management listener. Do not modify DNS, firewall, certificates, authentication, production traffic, SIP/carrier routing, emergency behavior, alert delivery, calls/DTMF, or retained evidence merely from this state file. Inspect first; preserve unrelated work; back up before mutations; validate; preserve rollback; stop at explicit credential/account/security/production boundaries.
