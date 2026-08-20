# Edge1 Operator Workspace Publication Acceptance — 2026-08-20

## Result

**PASS — WORKSPACE PUBLISHED / ACCEPTED**

The Christmas Island Worldwide ChatGPT workspace has the custom `Edge1 Operator` app enabled and usable from a fresh normal ChatGPT conversation.

## Live host/runtime acceptance

Accepted production revision:

`d326d4546abefa695a293266342a5c1075f010e2`

Immutable Edge1 Operator MCP runtime:

`/opt/edge1-operator-mcp-runtimes/d326d4546abe`

Persistent turn-state root:

`/var/lib/edge1-operator-mcp/turn-state`

Final host activation evidence:

`/var/lib/wwcx-deployment-evidence/edge1-operator-workspace-publication/20260820T070314Z`

The final host activation verified:

- MCP service active;
- unauthenticated local MCP requests return HTTP 401;
- `ProtectSystem=strict` remains enabled;
- state root is outside the immutable `/opt` tree and owned by `edge1-operator`;
- exactly 16 public tools are exposed;
- live tool metadata reports `access=read` with read-only, non-destructive, closed-world/local and idempotent annotations;
- internal `agent.turn.status` and `agent.turn.handoff` calls are rejected by the public dispatcher;
- Operations API is healthy with 27 fixed actions and `mutations_enabled=false`;
- Secure MCP Tunnel is active and enabled;
- Big Bird tunnel remains active.

## External ChatGPT acceptance

After final host activation, a fresh ChatGPT conversation successfully invoked the published workspace app.

Accepted user-facing checks:

1. `What is Edge1’s health?`
   - Edge1 Operator MCP reported healthy.
   - Operations API reported healthy.
   - action count reported as 27.
   - mutations reported disabled.

2. `Show me Edge1 network state, Asterisk status, and Big Bird status.`
   - network addresses/routes/listener classification returned successfully;
   - Asterisk diagnostics returned status `ok` through the bounded Asterisk-owned snapshot path;
   - Big Bird returned healthy, enabled and read-only with library integrity `ok`.

The live connector was independently rechecked after publication and again exposed exactly 16 Edge1 tools.

## Workspace permission decision

The operator intentionally selected a permissive ChatGPT workspace policy for this app:

- all app actions enabled;
- app approvals set to allow all / full access.

This decision affects ChatGPT confirmation behavior only. It does not broaden the server-side Edge1 authority. The live MCP server remains the enforcement boundary and still exposes only the reviewed bounded contract; the Operations API remains non-mutating.

The workspace UI may retain conservative/stale action-risk labels from its stored app snapshot. Those labels are not treated as evidence of actual Edge1 write authority; live server discovery, invocation behavior and the Operations API mutation flag are authoritative for the Edge1 runtime boundary.

## Persistent-state incident and resolution

During publication preparation, the newly pinned immutable MCP runtime initially failed because `TurnStateStore` defaulted to the `edge1-operator` home path under `/opt/edge1-management-interface/.local/state/...`. `ProtectSystem=strict` correctly prevented that write.

The accepted fix was not to weaken the sandbox. Production now sets:

`EDGE1_OPERATOR_TURN_STATE_ROOT=/var/lib/edge1-operator-mcp/turn-state`

and provisions the parent through:

`StateDirectory=edge1-operator-mcp`

with mode `0700`. The repository systemd unit now records this production requirement and tests protect it from regression.

## Non-blocking follow-up

The network listener classifier currently reports a number of `unknown-needs-attribution` listeners. These are attribution/inventory follow-up items, not a publication failure. They should be reconciled through the existing control-surface provenance process without making unrelated firewall, DNS, SIP, SSH or exposure changes.

## Final engineering interpretation

The Edge1 Operator workspace publication objective is complete when this record is merged with the systemd persistent-state fix and CI passes. No additional Edge1 service restart or workspace republish is required solely for this documentation closeout.
