# Current State

Last reconciled: 2026-08-19  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative repository branch: `main`

This file is the concise cross-workstream continuation index. Historical detail remains in dated acceptance, runbook, archive, and workstream-specific `.agent/` records.

## Repository state

Repository `main` after the Edge1 front-door live closeout is:

```text
8dc7b584dd765eb53de9f84a46472ce96316352a
```

The Edge1 production checkout used for the live front-door cutover remains at the implementation commit:

```text
74e7b1a6d19edebaf42c69df8d57838eb52eee78
```

The newer `main` commit is documentation/state closeout only. Do not advance a production checkout solely to make its HEAD match documentation unless the next approved workflow needs current repository assets and the working tree is clean.

## Edge1 public front door — LIVE / ACCEPTED

The 2026-08-19 public/default Edge1 front-door cutover is complete and must not be reopened without fresh contrary evidence.

Accepted behavior:

- raw/default IPv4 HTTP `/`: `302 -> https://ww.cx/time/`;
- unmatched Host HTTP `/`: `302 -> https://ww.cx/time/`;
- `edge1.ww.cx` HTTP `/`: existing `301 -> https://edge1.ww.cx/` preserved;
- `edge1.ww.cx` HTTPS `/` and `/index.html`: `302 -> https://ww.cx/time/`;
- `/edge1-status/`: preserved `200`;
- unknown HTTPS path: preserved `404`;
- raw HTTPS default-vhost HTTP behavior after TLS: unchanged;
- PBX/SIP named-host behavior preserved;
- Apache remained active on TCP 80/443;
- chronyd remained active on UDP 123 and TCP 4460.

Apache configtest passed before and after the controlled reload. Cache-busted browser verification confirmed the new root routing and preserved `/edge1-status/` / unknown-path behavior.

Protected rollback evidence:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh
```

Acceptance record:

`docs/control-surfaces/edge1-front-door-live-acceptance-20260819.md`

HTTP 302 is intentional. Promotion to 308 is optional future work and is not authorized automatically.

## Edge1 Operator / MCP

The server-side private Operator boundary is already verified live from 2026-08-18 evidence:

- `edge1-operator-mcp.service` installed, enabled, active;
- principal `edge1-operator`;
- MCP listener `127.0.0.1:8102` only;
- Operations API `127.0.0.1:8097` only;
- bearer file outside Git with restricted metadata verified without exposing its value;
- unauthenticated MCP request returned 401;
- authenticated initialize/tools/list/identity/health/Apache-status calls succeeded;
- 16 named parameterless read-only tools discovered;
- Operations API reported loopback true and mutations disabled.

The non-secret Secure MCP Tunnel host assets were staged and accepted on 2026-08-18. The tunnel service intentionally remains disabled/inactive until account/workspace enrollment provides the tunnel ID and runtime API key locally on Edge1.

The remaining permanent-Operator gate is the ChatGPT-side private transport/attachment:

1. authorized workspace/account developer/custom-app capability;
2. Secure MCP Tunnel enrollment without recording secrets in Git/chat;
3. ChatGPT tool scan matching the exact 16-tool contract;
4. ChatGPT-side `edge1.identity`, `edge1.health`, and approved diagnostic calls;
5. durable audit evidence plus tested stop/disable and account-side revocation path;
6. persistence enablement only after attended acceptance succeeds.

OpenAI guidance was rechecked on 2026-08-19 and continues to state that local/private-network MCP servers are not connected directly; Secure MCP Tunnel is the supported private-network path. No public Apache MCP proxy, WAN MCP listener, firewall opening, or MCP authentication weakening is part of the plan.

No direct `edge1.*` MCP connector is exposed to this ChatGPT session yet, so the ChatGPT attachment gate is not complete.

Detailed records:

- `docs/edge1-operator/08-mcp-integration-status.md`;
- `docs/edge1-operator/13-completion-status.md`;
- `docs/edge1-operator/14-secure-mcp-tunnel.md`.

## Control Surfaces

The public exposure-reduction/front-door portion is accepted. The existing private-source FreePBX Admin/UCP behavior was preserved by the 2026-08-19 front-door cutover. Earlier accepted Control Surfaces records state that ordinary WAN Admin/UCP access was denied while approved private paths remained available; today's connected browser is part of the private management environment and therefore is not independent WAN denial evidence.

The remaining Control Surfaces work is limited to:

- permanent ChatGPT Operator transport/attachment described above;
- final reconciliation of native Asterisk/Kamailio/FreePBX diagnostic-card degraded states without weakening service hardening or widening permissions;
- any temporary/private FreePBX native-session mechanism only after redirects, cookies, WebSockets, CSP, X-Frame-Options, expiry, revocation, CSRF, and audit behavior are proven.

## Security-boundary completion work

The merged security-boundary inventory bundle remains pending live execution through an approved authenticated Edge1 path.

Next safe step is read-only:

`sudo bash tools/security/edge1-security-boundary-live-inventory.sh`

It must create protected evidence under `/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory/`, retain unknown artifacts rather than altering them, and report no live configuration or traffic-control changes.

Only after review of that evidence may restricted-release/authentication/public-tree work proceed. DNS, firewall, certificate, authentication, listener, or traffic changes remain separately gated.

## Asterisk / alerting warning follow-up

The offline alerting laboratory remains accepted and isolated. The next safe action is the existing read-only warning audit:

`tools/alerting/asterisk_warning_followup_audit.sh`

It must reconcile, without changing configuration:

- PJSIP CLI transport visibility versus Asterisk-owned loopback UDP `127.0.0.1:5061`;
- Asterisk boot persistence across the SysV/systemd wrapper state;
- TCP `8089` bind scope, local TLS identity, firewall references, and operational need.

Warnings do not authorize listener, startup-policy, certificate, or firewall changes.

## DTMF provider work

Provider-response work remains externally blocked:

- direct provider technical response not yet recorded;
- matrix update remains blocked;
- live call/DTMF testing remains separately authorization-gated.

When a response arrives, retain the original only in the restricted mailbox, create a sanitized worksheet, classify all nine answers by scope/evidence strength, and run the repository validators before any matrix update.

## Communications Relay / News Reader

This workstream is sealed. Do not reopen it unless new contrary evidence appears.

Accepted production checkout remains intentionally separate from current repository `main`. See the Communications Relay acceptance and archive-seal records for exact revisions and protected evidence.

## Current continuation order

1. Keep the accepted front door unchanged.
2. Complete repository state reconciliation and keep `main` authoritative for continuation docs.
3. Advance the permanent Operator only through the Secure MCP Tunnel/account boundary; do not expose MCP publicly.
4. Run and review the security-boundary inventory.
5. Run and review the Asterisk warning follow-up audit.
6. Reconcile remaining Control Surfaces diagnostic degradation from evidence.
7. Leave DTMF provider work pending until external response arrives.
8. Preserve sealed/accepted workstreams unless new evidence requires reopening.

## Safety boundary

Do not expose credentials or secret values. Do not change DNS, firewall, certificates, authentication policy, public listeners, production traffic, SIP/carrier routing, emergency behavior, alert delivery, call/DTMF transmission, or retained evidence/data from this state record alone. Inspect first; back up before mutations; use the smallest change; validate; preserve rollback; stop at explicit credential/account/security/production approval boundaries.
