# Edge1 Secure MCP Tunnel

Last reconciled: 2026-08-20
Status: **LIVE / ACCEPTED / PERSISTENT**; production-clean Operator closeout still requires deployment and live verification of the focused commissioning fixes.

## Accepted transport state

The Secure MCP Tunnel is already commissioned. Do not repeat initial setup unless live evidence proves regression.

Accepted live state:

- host `edge1.ww.cx`;
- `edge1-secure-mcp-tunnel.service` active and enabled;
- `edge1-operator-mcp.service` active;
- `bigbird-ai-tunnel.service` active and healthy;
- local Edge1 MCP endpoint remains `127.0.0.1:8102/mcp` and rejects unauthenticated requests;
- Secure MCP Tunnel `/healthz` is live and `/readyz` is ready;
- stop/start acceptance passed before persistence was accepted;
- ChatGPT -> Secure MCP Tunnel -> Edge1 works end-to-end;
- `edge1.identity` confirms hostname `edge1.ww.cx`, principal `edge1-operator`, service ready;
- `edge1.health` confirms Operations API loopback-only and `mutations_enabled=false`;
- Big Bird remained healthy through activation;
- the shared tunnel-client was not upgraded/replaced merely to address the reviewed optional OAuth metadata doctor false-negative.

Secret tunnel identifiers, runtime API keys, MCP bearer values, and other credentials are deliberately excluded from this runbook and evidence.

## Boundary that must remain true

The tunnel is an outbound transport only. It must not require a public Edge1 MCP listener, firewall/DNS change, Apache proxy, weaker MCP authentication, or Big Bird reconfiguration.

The local Operator remains a named, bounded, parameterless tool surface. There is no generic `edge1.exec` or arbitrary-command path. The Operations API remains loopback-only and its mutation gate remains disabled.

## Public Edge1 Operator tool contract

The application contract is exactly:

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

Repository-internal/newer protocol tools such as `agent.turn.status` or `agent.turn.handoff` are not part of this app and must not be exposed by a deployment. No generic execution or write tool may be added implicitly.

Every published tool must carry standard MCP annotations that truthfully describe the bounded surface. For these 16 local diagnostics the reviewed contract is read-only, non-destructive, closed-world/local, and idempotent.

## 2026-08-20 closeout findings

### Network diagnostics

Live snapshot evidence proves the current Operations API sandbox prevents `ip` from opening the netlink socket:

```text
Cannot open netlink socket: Address family not supported by protocol
```

The fixed actions `network.addresses` and `network.routes` therefore fail and `edge1.network_state` returns a bounded runtime error. The smallest reviewed repository fix is to add `AF_NETLINK` to the service's `RestrictAddressFamilies` only. It does **not** add `CAP_NET_ADMIN`, arbitrary command execution, mutation authority, or a non-loopback listener.

### Asterisk diagnostics

Asterisk service/passive diagnostics remain healthy, and the direct host warning audit completed with Warnings: 0 and Failures: 0. The fixed native Asterisk CLI probes remain privilege-gated from the Operations API principal and report inability to connect to the local Asterisk control socket.

Preserve passive fallback. Do not grant unrestricted Asterisk CLI or shell authority. A native diagnostic path must use only a narrowly reviewed helper, socket-group permission, or exact sudo allowlist after current control-socket ownership/mode is inspected. This limitation must not be misreported as an Asterisk service failure.

### Security-boundary preserved artifacts

The reviewed preserved set is:

- `network-sensor/data/network-sensor.json` — generated JSON; validate type/structure, not stale historical size/hash;
- `network-sensor/index.html` — repository-static; must match `src/web/network-sensor/index.html`;
- `operations-center/snmp.html` — preserved unresolved artifact; do not overwrite simply to manufacture Git provenance;
- `snmp/operations-snmp.json` — generated JSON; validate type/structure, not stale historical size/hash;
- `security-correlation.json` — reviewed compatibility symlink with exact contained target validation.

The classifier must fail closed on unexpected preserved paths, non-regular files, unsafe permissions, malformed generated JSON, static source mismatch, or symlink target drift.

## Repository/live revision discipline

During closeout, remote `main`, live `/opt` source, and the MCP runtime diagnostic reported different revisions. They must be reconciled deliberately before deployment; do not reset/switch live branches based on assumption.

The focused closeout branch was based on remote `main` at:

```text
408bf253d308da1f310f82c9147c4184ec16d8cc
```

The live `/opt/edge1-management-interface` snapshot remained clean `main` at:

```text
f3a20fb60783412758ab322a2f1a43defb2684c7
```

The MCP runtime `edge1.git_state` reported:

```text
7496da7550ee46ef81142081b0a63fced7894e90
```

No live branch switch or reset is authorized by this documentation.

## Validation required after deploying the reviewed closeout

Repository/unit validation must pass for every changed component. Then verify through ChatGPT at minimum:

- `edge1.identity`
- `edge1.health`
- `edge1.network_state`
- `edge1.asterisk_status`
- `edge1.services`
- `edge1.bigbird_status`
- `edge1.operations_status`
- `edge1.git_state`
- `edge1.config_digest`

As appropriate, also verify snapshot, inventory, disk, Apache, telephony, messaging, and time-authority status.

Require throughout:

- tunnel active and enabled;
- MCP loopback-only and bearer-protected;
- Operations API loopback-only;
- `mutations_enabled=false`;
- Big Bird healthy;
- no unintended public listener or authentication change;
- exactly 16 published Edge1 Operator tools with truthful safety annotations.

## Rollback

Stop the tunnel:

```sh
systemctl stop edge1-secure-mcp-tunnel.service
```

Disable persistence and stop it:

```sh
systemctl disable --now edge1-secure-mcp-tunnel.service
```

Tunnel rollback must not remove/replace the shared tunnel-client or alter Big Bird, firewall, DNS, SSH, Apache, certificates, SIP, SNMP, account policy, or unrelated production services.

## Publication gate

Tunnel acceptance does not itself authorize workspace publication. Publication may be considered only after the reviewed closeout revision is tested and deployed, the 16-tool contract/annotations are confirmed from ChatGPT, `edge1.network_state` works, Asterisk native diagnostics either work through a bounded mechanism or are explicitly accepted as a limitation, and final non-secret audit evidence is complete.
