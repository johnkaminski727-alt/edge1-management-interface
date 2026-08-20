# Edge1 Operator MCP post-deployment acceptance — 2026-08-20

## Verdict

**READY FOR WORKSPACE PUBLICATION** from the Edge1 engineering/operations readiness perspective.

This verdict is based on successful repository CI, reviewed merge, backup-first live deployment, immutable Operations API runtime repin, and authoritative post-deployment validation through the live Edge1 Operator MCP. It does not itself publish the app or change workspace policy.

## Accepted revision and deployment evidence

Reviewed and merged revision:

`d326d4546abefa695a293266342a5c1075f010e2`

Primary checkout after deployment:

- `/opt/edge1-management-interface`
- clean `main`
- HEAD `d326d4546abefa695a293266342a5c1075f010e2`

Immutable Operations API runtime:

- `/opt/edge1-operations-api-runtimes/d326d4546abe`
- detached clean worktree at the same full revision
- runtime acceptance evidence: `/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260820T045417Z`
- runtime rollback: `/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260820T045417Z/rollback.sh`

Commissioning closeout deployment evidence:

- `/var/lib/wwcx-deployment-evidence/edge1-operator-commissioning-closeout/20260820T045156Z`

Pre-fast-forward safety branch:

- `safety/edge1-operator-pre-closeout-20260820T045153Z`

No secret values are recorded here.

## Live post-deployment acceptance

### Edge1 Operator / Operations API

- `edge1.health`: status OK.
- Operations API remains loopback-only.
- Operations API reports 27 fixed actions and `mutations_enabled=false`.
- Edge1 Operator identity is ready on `edge1.ww.cx` as principal `edge1-operator`.
- Current connected app surface exposes exactly 16 Edge1 Operator tools.
- Repository protocol at the accepted revision defines exactly those 16 tools with `readOnlyHint=true`, `destructiveHint=false`, `openWorldHint=false`, and `idempotentHint=true`.
- Public call dispatch is allowlisted to the same 16 names; internal `agent.turn.*` adapter capabilities are not part of the public app contract.

### Network diagnostics

`edge1.network_state` now succeeds for all three bounded actions:

- `network.addresses` — succeeded, audit event `ea98a2b2-82c8-4272-8e05-863b6961660d`;
- `network.routes` — succeeded, audit event `f838c291-5958-4b44-8e06-e0e5a000cc21`;
- `control_surfaces.listeners` — succeeded, audit event `d3c7e1c0-7d9d-4879-85b0-17b73b4cce12`.

This confirms the bounded `AF_NETLINK` systemd change fixed the prior read-only netlink failure without adding `CAP_NET_ADMIN`.

### Asterisk native diagnostics

`edge1.asterisk_status` is fully successful, audit event `03ad0a95-ab61-4bb0-9f1e-4b6c8b642e47`.

Accepted properties:

- overall status `ok`;
- `native_cli_status=ok`;
- source `asterisk-owned-fixed-snapshot`;
- all seven fixed read-only CLI checks succeeded;
- snapshot contract `wwcx.edge1-asterisk-readonly-snapshot.v1`;
- snapshot owner `asterisk`;
- reader group `bigbird-audit`;
- mode `0640`;
- caller parameters not accepted;
- snapshot was fresh during acceptance;
- passive fallback was not required.

The solution does not add `wwadmin` to the `asterisk` group, does not add sudoers authority, does not expose arbitrary Asterisk CLI, and does not add a network listener.

### Repository/runtime reconciliation

`edge1.git_state` now reports the immutable Operations API runtime at the accepted revision:

- repository status event `53b0e5df-4af4-4453-a8c2-14d3fa69a294`;
- repository head event `85d84c21-d5f7-4a67-b9cc-edc6dd6745ad`;
- HEAD `d326d4546abefa695a293266342a5c1075f010e2`.

The authoritative host snapshot independently reports the shared primary checkout clean on `main` at the same accepted revision, audit event `d6a58507-74e5-4671-aba7-f8207cd5a2d4`.

The intentional distinction is therefore resolved cleanly: the shared engineering checkout is `main` at the accepted revision, while the Operations API runs from a detached immutable worktree at the same revision.

### Configuration digest

`edge1.config_digest` succeeded, audit event `1654a4fc-889e-4f3e-acce-7a48839e3c05`, and now covers the expanded commissioning boundary including:

- Operations API allowlist and systemd unit;
- Operator MCP service;
- public MCP protocol and entrypoint dispatch boundary;
- Asterisk snapshot producer and consumer;
- Asterisk snapshot service and timer.

### Service and adjacent-system health

`edge1.services` succeeded, audit event `0cbc09c8-a6a5-4389-8725-98a9129e8367`.

Confirmed active after deployment:

- `edge1-operations-api.service`;
- `edge1-operator-mcp.service`;
- `edge1-secure-mcp-tunnel.service`;
- `bigbird-ai-gateway.service`;
- `bigbird-ai-tunnel.service`;
- Asterisk, Apache, Kamailio and other pre-existing active services.

The two pre-existing BigBird connector lifecycle units remain failed exactly as before this closeout and were not modified:

- `bigbird-edge1-connector-maintenance.service`;
- `bigbird-edge1-connector.service`.

Big Bird itself remains healthy and read-only; `edge1.bigbird_status` health audit event `2400ac38-3104-4cce-bf37-0131abe62eb2`, tool-registry audit event `c8f3220e-b2d2-4a8f-94f7-fc31d6eab28c`.

Additional adjacent-system checks:

- telephony overall healthy; audit event `df95586c-0ed1-4170-9f60-9ea2efdc67c6`;
- messaging health OK; audit event `6fe9604a-86d2-40db-abd9-2fd6ee22101c`;
- time authority healthy with all ten observed sources reachable; audit event `0d104a9d-f89f-44b1-946d-c3bc9d6a4d15`.

## Security-boundary acceptance

The accepted state preserves all commissioning constraints:

- no generic exec/write MCP tool;
- exactly 16 public Edge1 tools;
- Operations API mutations disabled;
- Operations API remains loopback-only;
- local MCP remains bounded behind the existing authenticated Secure MCP Tunnel;
- no firewall, DNS, SSH, Apache, certificate, SIP, SNMP, account, authentication, or Big Bird configuration change was required;
- no shared tunnel-client upgrade was performed;
- no secret values were exposed or recorded;
- Asterisk privilege was solved by a fixed producer/snapshot boundary rather than broad socket authority;
- protected deployment evidence and rollback records exist on Edge1.

## Repository validation

PR #466 passed all four required GitHub Actions gates before merge:

- Validate repository;
- Edge1 operations API;
- Validate Edge1 Control Surfaces;
- Edge1 Operator Validation.

PR #466 merged normally without force push or history rewriting. Concurrent `main` changes were inspected and were limited to unrelated Business159 tunnel assets.

## Publication gate

All engineering gates defined by the commissioning closeout are now satisfied.

**Engineering publication verdict: READY FOR WORKSPACE PUBLICATION.**

Actual workspace publication remains a separate administrative/product action. Publishing must not broaden the 16-tool contract, add write authority, alter authentication, or change the accepted tunnel/runtime boundaries.

## Rollback references

Operations API immutable-runtime rollback:

`/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260820T045417Z/rollback.sh`

Commissioning closeout unit rollback is preserved inside:

`/var/lib/wwcx-deployment-evidence/edge1-operator-commissioning-closeout/20260820T045156Z/`

Secure MCP Tunnel emergency stop remains:

```sh
systemctl stop edge1-secure-mcp-tunnel.service
```

Disable persistence only if intentionally rolling back the accepted tunnel itself:

```sh
systemctl disable --now edge1-secure-mcp-tunnel.service
```
