# Edge1 Operator Completion Status

Last reconciled: 2026-08-20

## Current state

The Edge1 Secure MCP Tunnel, Edge1 Operator MCP commissioning, and ChatGPT workspace publication are **LIVE / ACCEPTED / PERSISTENT**.

Engineering publication verdict: **WORKSPACE PUBLISHED / ACCEPTED**.

The Christmas Island Worldwide workspace has the custom `Edge1 Operator` app enabled. All 16 actions are enabled and the workspace approval policy is intentionally permissive (`Allow all`) by operator preference. This workspace policy does not broaden the server-side authority: the live MCP server still exposes only the reviewed bounded tool surface and the Operations API still reports `mutations_enabled=false`.

## Accepted runtime revision

Accepted production code revision:

`d326d4546abefa695a293266342a5c1075f010e2`

Primary engineering repository `main` may contain later documentation or unrelated reviewed changes; production Edge1 Operator execution remains pinned to the accepted immutable runtime below until a separately reviewed runtime upgrade is performed.

Immutable Edge1 Operator MCP runtime:

- `/opt/edge1-operator-mcp-runtimes/d326d4546abe`
- detached clean worktree at the accepted production revision

Dedicated persistent turn-state root:

- `/var/lib/edge1-operator-mcp/turn-state`
- created through systemd `StateDirectory=edge1-operator-mcp`
- owned by `edge1-operator`
- runtime directory mode `0700`
- `ProtectSystem=strict` remains enabled

Immutable Operations API runtime:

- `/opt/edge1-operations-api-runtimes/d326d4546abe`
- detached clean worktree at the same accepted production revision

Detailed pre-publication engineering evidence is recorded in:

`docs/edge1-operator/17-post-deployment-acceptance-20260820.md`

Workspace publication closeout is recorded in:

`docs/edge1-operator/18-workspace-publication-acceptance-20260820.md`

## Accepted live behavior

Verified through the live Edge1 Operator MCP after workspace publication:

- identity ready on `edge1.ww.cx` as principal `edge1-operator`;
- Operations API healthy, loopback-only, 27 fixed actions, `mutations_enabled=false`;
- Secure MCP Tunnel active and persistent;
- Edge1 Operator MCP active from the immutable runtime;
- exactly 16 public Edge1 tools are exposed;
- all public tools use read-only, non-destructive, closed-world/local, idempotent MCP annotations at the live server boundary;
- public call dispatch rejects internal `agent.turn.*` capabilities;
- no generic execution or write MCP tool is exposed;
- `edge1.network_state` succeeds for addresses, routes and listener classification;
- Asterisk native diagnostics succeed through the bounded `asterisk`-owned snapshot mechanism;
- Asterisk snapshot remains `asterisk:bigbird-audit 0640`, fresh and no-parameter;
- `wwadmin` is not granted Asterisk control-socket authority;
- Big Bird remains healthy and read-only;
- workspace use was accepted from a fresh ChatGPT conversation without approval prompts under the operator-selected permissive app policy;
- the dedicated turn-state root prevents the MCP process from attempting writes under the read-only `/opt/edge1-management-interface` tree.

## Commissioning design decisions

### Network diagnostics

The Operations API sandbox permits `AF_NETLINK` only as the additional address family required by fixed read-only `ip -json` probes. Capability bounding and ambient capability sets remain empty; `CAP_NET_ADMIN` is not granted.

### Public MCP contract

The externally published contract is exactly these 16 tools:

1. `edge1.identity`
2. `edge1.health`
3. `edge1.snapshot`
4. `edge1.inventory`
5. `edge1.services`
6. `edge1.network_state`
7. `edge1.disk_state`
8. `edge1.bigbird_status`
9. `edge1.operations_status`
10. `edge1.apache_status`
11. `edge1.asterisk_status`
12. `edge1.telephony_status`
13. `edge1.messaging_status`
14. `edge1.time_authority_status`
15. `edge1.git_state`
16. `edge1.config_digest`

Internal `agent.turn.status` and `agent.turn.handoff` may remain inside lower-level adapter code for explicitly internal workflows but are excluded at both public discovery and public call dispatch.

### Workspace permissions

The workspace app is intentionally configured with all actions enabled and permissive approval behavior. Treat that as a ChatGPT product-layer usability choice, not as the Edge1 security boundary. The authoritative enforcement boundary remains the authenticated MCP service, the exact public allowlist, the loopback-only Operations API, fixed action definitions, and `mutations_enabled=false`.

### Persistent turn state

`TurnStateStore` supports `EDGE1_OPERATOR_TURN_STATE_ROOT`. Production sets this to `/var/lib/edge1-operator-mcp/turn-state` through the systemd unit and provisions the parent with `StateDirectory=edge1-operator-mcp`. This preserves durable SQLite state without weakening `ProtectSystem=strict` or granting write access to the immutable code/runtime tree.

### Asterisk diagnostics

Direct `wwadmin` access to `/var/run/asterisk/asterisk.ctl` was deliberately rejected because the socket is a general CLI control channel. The accepted mechanism instead runs exactly seven fixed read-only Asterisk CLI probes as the existing `asterisk` account and publishes a sanitized bounded snapshot for read-only consumption by the Operations API through the existing `bigbird-audit` group.

No sudoers rule, shell authority, arbitrary Asterisk command, new listener, or `wwadmin` membership in group `asterisk` is introduced.

### Immutable runtimes

Production Operations API and Edge1 Operator MCP execution remain pinned to clean detached worktrees rather than the shared engineering checkout. This preserves the runtime-isolation design while allowing `main` to advance independently for documentation and separately reviewed work.

## Known non-blocking follow-up

Listener classification currently includes a set of `unknown-needs-attribution` listeners. These are inventory/provenance cleanup items, not publication or service-health failures. They should be reconciled through the existing control-surface attribution process without changing firewall, DNS, SIP, SSH, or service exposure merely to make the count disappear.

## Known pre-existing conditions not changed by this closeout

These Big Bird connector lifecycle units remain failed and were already failed before commissioning closeout:

- `bigbird-edge1-connector-maintenance.service`;
- `bigbird-edge1-connector.service`.

Big Bird gateway/tunnel/service/worker health is otherwise good, and these failures were intentionally not disturbed as part of the Edge1 Operator commissioning scope.

## Evidence and rollback

Commissioning deployment evidence:

`/var/lib/wwcx-deployment-evidence/edge1-operator-commissioning-closeout/20260820T045156Z`

Immutable Operations API runtime acceptance evidence:

`/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260820T045417Z`

Workspace publication host activation evidence:

`/var/lib/wwcx-deployment-evidence/edge1-operator-workspace-publication/20260820T070314Z`

Pre-deployment safety branch:

`safety/edge1-operator-pre-closeout-20260820T045153Z`

Tunnel emergency stop:

```sh
systemctl stop edge1-secure-mcp-tunnel.service
```

Disable tunnel persistence only for an intentional tunnel rollback:

```sh
systemctl disable --now edge1-secure-mcp-tunnel.service
```

Do not alter the shared tunnel-client, Big Bird, firewall, DNS, SSH, Apache, certificates, SIP, SNMP, accounts or authentication as part of routine Operator rollback.
