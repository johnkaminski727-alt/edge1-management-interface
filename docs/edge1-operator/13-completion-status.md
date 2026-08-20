# Edge1 Operator Completion Status

Last reconciled: 2026-08-20

## Current state

The Secure MCP Tunnel activation itself is **LIVE / ACCEPTED / PERSISTENT**. Do not repeat initial staging or activation unless live evidence shows regression.

Verified live through the Edge1 Operator MCP on 2026-08-20:

- host identity: `edge1.ww.cx`, principal `edge1-operator`, service ready;
- `edge1-secure-mcp-tunnel.service` active and enabled;
- `edge1-operator-mcp.service` active;
- `bigbird-ai-tunnel.service` active and Big Bird health OK;
- local Edge1 MCP remains loopback-only and bearer-protected; unauthenticated access is rejected;
- Operations API remains loopback-only with `mutations_enabled=false`;
- ChatGPT reaches Edge1 end-to-end through the Secure MCP Tunnel;
- the currently discovered app surface is exactly the intended 16 named Edge1 tools;
- no generic execution tool is exposed.

The tunnel transport is commissioned. Workspace-wide publication remains a separate gate.

## 2026-08-20 commissioning closeout

A focused repository branch, `edge1/operator-mcp-commissioning-closeout-20260820`, was created from remote `main` at `408bf253d308da1f310f82c9147c4184ec16d8cc` without moving the live Edge1 checkout.

The closeout branch addresses these bounded issues:

1. **Network diagnostics sandbox** — `edge1.network_state` and inventory probes fail because `ip` cannot open an AF_NETLINK socket inside `edge1-operations-api.service`. The proposed unit change adds only `AF_NETLINK` to `RestrictAddressFamilies`; the fixed action allowlist, empty capability sets, loopback binding, and `mutations_enabled=false` remain unchanged.
2. **Public MCP contract** — the repository protocol had accumulated newer `agent.turn.*` protocol tools. The public Edge1 Operator contract is now explicitly locked to the intended 16 tools only.
3. **Standard MCP annotations** — each public Edge1 tool is annotated read-only, non-destructive, closed-world/local, and idempotent where factually correct. The custom `access=read` marker is retained as supplemental metadata.
4. **Security-boundary residual classifier** — classification now matches the actual preserved records: repository-static `network-sensor/index.html`; generated JSON `network-sensor/data/network-sensor.json` and `snmp/operations-snmp.json`; explicitly preserved unresolved `operations-center/snmp.html`; and the reviewed `security-correlation.json` compatibility symlink. Dynamic JSON is not compared with stale historical size/hash snapshots, and the unresolved HTML is not overwritten to manufacture provenance.

Regression tests protect the exact 16-tool surface, annotations, netlink-without-CAP_NET_ADMIN sandbox, and fail-closed residual classifications.

## Repository/live provenance reconciliation

Three revisions are intentionally distinguished:

- current remote `main` observed during closeout: `408bf253d308da1f310f82c9147c4184ec16d8cc`;
- live `/opt/edge1-management-interface` snapshot: clean `main` at `f3a20fb60783412758ab322a2f1a43defb2684c7`;
- `edge1.git_state` runtime-reported revision: `7496da7550ee46ef81142081b0a63fced7894e90`.

Do not treat those as interchangeable. The live `/opt` checkout was not switched, reset, or overwritten during this closeout. Before deployment, identify the MCP runtime/package provenance for `7496da7...` and deploy the reviewed closeout revision deliberately rather than by branch guessing.

## Asterisk diagnostic limitation

Asterisk itself remains healthy by service/passive evidence and the earlier direct host warning audit (Warnings: 0, Failures: 0). The MCP-side fixed native CLI probes still cannot connect to the Asterisk control socket under the Operations API principal.

Do not grant unrestricted Asterisk CLI or shell access. Preserve passive fallback. A native fix must be limited to a reviewed read-only helper/socket-group/sudo allowlist mechanism after live socket ownership/mode evidence is captured. Until that bounded mechanism is deployed and verified through ChatGPT, native Asterisk CLI diagnostics remain an explicitly accepted commissioning limitation, not evidence of Asterisk failure.

## Rollback

Stop the accepted tunnel without changing other Edge1 services:

```sh
systemctl stop edge1-secure-mcp-tunnel.service
```

Disable persistence and stop it:

```sh
systemctl disable --now edge1-secure-mcp-tunnel.service
```

Rollback must not remove or replace the shared tunnel-client, restart/reconfigure Big Bird, expose the local MCP publicly, or alter firewall, DNS, Apache, SSH, SIP, SNMP, certificates, accounts, or authentication.

## Publication gate

Do **not** publish the Edge1 Operator app workspace-wide until all of these are true on the deployed reviewed revision:

- all intended 16 tools work, or any remaining bounded limitation is explicitly accepted;
- standard MCP annotations accurately represent every exposed tool;
- `tools/list` exposes exactly the 16 intended tools and no `agent.turn.*`, generic exec, or write surface;
- `edge1.network_state` succeeds after the AF_NETLINK sandbox fix;
- Asterisk native read-only diagnostics either succeed through a narrowly scoped mechanism or the limitation is explicitly accepted for publication;
- repository/unit tests and live acceptance checks pass;
- tunnel remains active+enabled, loopback-only local MCP remains bearer-protected, Operations API remains loopback-only with mutations disabled, and Big Bird remains healthy;
- final evidence records the tested revision and meaningful audit event IDs without secret values.

Until those deployment/live-validation gates pass, the correct publication verdict is **NOT READY FOR WORKSPACE PUBLICATION**, even though the Secure MCP Tunnel itself is accepted and persistent.
