# Edge1 Operator Completion Status

Last reconciled: 2026-08-20

## Current state

The Edge1 Secure MCP Tunnel and Edge1 Operator MCP commissioning are **LIVE / ACCEPTED / PERSISTENT**.

Engineering publication verdict: **READY FOR WORKSPACE PUBLICATION**.

Actual workspace publication remains a separate administrative/product action and must not broaden the accepted tool, authentication, or runtime boundaries.

## Accepted revision

Merged and deployed revision:

`d326d4546abefa695a293266342a5c1075f010e2`

Primary engineering checkout:

- `/opt/edge1-management-interface`
- clean `main`
- accepted revision above

Immutable Operations API runtime:

- `/opt/edge1-operations-api-runtimes/d326d4546abe`
- detached clean worktree at the same accepted revision

Final detailed evidence is recorded in:

`docs/edge1-operator/17-post-deployment-acceptance-20260820.md`

## Accepted live behavior

Verified through the live Edge1 Operator MCP after deployment and immutable-runtime repin:

- identity ready on `edge1.ww.cx` as principal `edge1-operator`;
- Operations API healthy, loopback-only, 27 fixed actions, `mutations_enabled=false`;
- Secure MCP Tunnel active and persistent;
- Edge1 Operator MCP active;
- exactly 16 public Edge1 tools are exposed;
- all public tools use read-only, non-destructive, closed-world/local, idempotent MCP annotations;
- public call dispatch rejects internal `agent.turn.*` capabilities;
- no generic execution or write MCP tool is exposed;
- `edge1.network_state` succeeds for addresses, routes and listener classification;
- Asterisk native diagnostics succeed through the bounded `asterisk`-owned snapshot mechanism;
- Asterisk snapshot remains `asterisk:bigbird-audit 0640`, fresh and no-parameter;
- `wwadmin` is not granted Asterisk control-socket authority;
- Big Bird remains healthy and read-only;
- telephony, messaging and time-authority checks are healthy;
- repository/runtime provenance is reconciled to the accepted revision;
- expanded configuration digest covers the Operator public contract and Asterisk helper boundary.

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

### Asterisk diagnostics

Direct `wwadmin` access to `/var/run/asterisk/asterisk.ctl` was deliberately rejected because the socket is a general CLI control channel. The accepted mechanism instead runs exactly seven fixed read-only Asterisk CLI probes as the existing `asterisk` account and publishes a sanitized bounded snapshot for read-only consumption by the Operations API through the existing `bigbird-audit` group.

No sudoers rule, shell authority, arbitrary Asterisk command, new listener, or `wwadmin` membership in group `asterisk` is introduced.

### Immutable Operations API runtime

Production Operations API execution remains pinned to a clean detached worktree rather than the shared engineering checkout. This preserves the established runtime-isolation design while keeping both the immutable runtime and shared checkout on the same reviewed revision.

## Known pre-existing conditions not changed by this closeout

These Big Bird connector lifecycle units remain failed and were already failed before commissioning closeout:

- `bigbird-edge1-connector-maintenance.service`;
- `bigbird-edge1-connector.service`.

Big Bird gateway/tunnel/service/worker health is otherwise good, and these failures were intentionally not disturbed as part of the Edge1 Operator commissioning scope.

## Evidence and rollback

Commissioning deployment evidence:

`/var/lib/wwcx-deployment-evidence/edge1-operator-commissioning-closeout/20260820T045156Z`

Immutable runtime acceptance evidence:

`/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260820T045417Z`

Immutable runtime rollback:

`/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260820T045417Z/rollback.sh`

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
