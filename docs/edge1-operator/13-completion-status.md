# Edge1 Operator Completion Status

Last reconciled: 2026-08-19

## Purpose

Track the transition from the verified live Edge1 server-side Operator to a permanently available private authenticated ChatGPT Edge1 operator.

## Repository and server-side foundation — complete

The following are complete and must not be rebuilt merely because the ChatGPT attachment remains pending:

- architecture and authority/risk boundaries;
- loopback HMAC/replay-protected Operations API and fixed server-side allowlist;
- fixed non-mutating Control Surfaces diagnostics;
- read-only Control Surfaces live-inventory runner with safety tests and CI;
- named parameterless MCP read-only tool contract;
- fixed Operations API client restricted to loopback and compile-time actions;
- runtime mappings from MCP tools to fixed read-only Operations API actions;
- internal `tools/list` / `tools/call` dispatch;
- removal of MCP-visible generic `edge1.exec` and generic arbitrary-command execution scaffolding;
- focused bounded-tool validation.

Fresh production verification established:

- `edge1-operator-mcp.service` loaded, enabled, active, running;
- service principal `edge1-operator`;
- MCP listener `127.0.0.1:8102` only;
- Operations API listener `127.0.0.1:8097` only;
- hardened service settings retained (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome=true`);
- bearer token metadata restricted; token value not exposed;
- unauthenticated MCP request -> HTTP 401;
- authenticated MCP initialize/tools/list -> HTTP 200;
- 16 named parameterless read-only tools discovered;
- `edge1.identity`, `edge1.health`, and `edge1.apache_status` succeeded;
- Operations API reported loopback true and `mutations_enabled=false`.

The production server-side MCP boundary is therefore **verified live**.

## Public Edge1 state — LIVE / ACCEPTED

The 2026-08-19 public front-door work is accepted and independent of the private MCP transport. Canonical ordinary public destination is `https://ww.cx/time/`; operational/non-root routes, PBX/SIP behavior, Apache listeners, chronyd listeners, and raw HTTPS handling were preserved. The private Operator must not be exposed through the public front door.

Protected rollback evidence remains under:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
```

## Secure MCP Tunnel state

Non-secret host staging was accepted on 2026-08-18. By 2026-08-19 the authorized account-side tunnel selection and local credential provisioning were also complete without recording secret values:

- existing official `tunnel-client` retained unchanged;
- Big Bird tunnel remained active/unchanged;
- Edge1 tunnel config, launcher, and unit remain isolated in the Edge1 namespace;
- `/etc/edge1-tunnel/tunnel-id` and `/etc/edge1-tunnel/runtime-api-key` exist with restricted `root:edge1-operator` mode `0640` metadata;
- `edge1-secure-mcp-tunnel.service` remains disabled/inactive;
- no second persistent tunnel process has been accepted yet;
- no public listener, firewall/DNS change, Apache proxy, MCP auth change, or Operator restart was introduced.

The installed shared tunnel-client is pinned to:

```text
0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144
sha256=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100
```

Its raw `doctor` has one reviewed old-build false negative: exit code `2`, with `oauth_metadata` as the sole failed check because the Edge1 bearer-authenticated MCP server intentionally does not publish OAuth protected-resource metadata. Do not add synthetic OAuth endpoints or replace the shared tunnel-client merely to make this old doctor green.

The required preactivation gate is now:

```text
deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh
```

That validator is fail-closed and must report:

```text
EDGE1_TUNNEL_COMPAT_DOCTOR=PASS
```

before attended activation is considered. It verifies the exact reviewed binary and installed asset hashes/metadata, unauthenticated MCP 401, authenticated GET `/mcp` 405, OAuth metadata candidates 404, and the exact reviewed raw-doctor result. Unexpected raw-doctor success from the pinned old build is drift and requires re-review.

`deploy/edge1-tunnel/install-edge1-secure-mcp-tunnel.sh --apply` is staging-only and must refuse when the tunnel is active or enabled; it must not stop or disable an accepted tunnel on a later rerun.

See:

- `docs/edge1-operator/14-secure-mcp-tunnel.md`
- `docs/edge1-operator/15-tunnel-doctor-compatibility-20260819.md`

## Remaining completion gate — private ChatGPT attachment

Remaining tasks:

1. confirm the applicable developer/custom-app capability in the authorized ChatGPT workspace/account;
2. merge the reviewed preactivation hardening and fast-forward the clean Edge1 checkout;
3. run the compatibility validator and require `EDGE1_TUNNEL_COMPAT_DOCTOR=PASS`;
4. obtain explicit approval for attended tunnel activation;
5. start `edge1-secure-mcp-tunnel.service` attended without enabling persistence;
6. verify the tunnel's dynamic loopback `/healthz` and `/readyz`, Big Bird health, and unchanged Edge1 listener boundary;
7. scan tools from ChatGPT and verify exactly the expected 16 named parameterless read-only tools;
8. prove ChatGPT-side `edge1.identity`, `edge1.health`, and approved diagnostics with durable audit evidence;
9. test attended stop plus documented account-side revocation path;
10. enable persistence only after attended acceptance passes;
11. record final closeout.

Account sign-in, private activation links, credential values, and account-side revocation remain explicit human boundaries and must not be pasted into Git or chat.

No direct `edge1.*` MCP connector is exposed to the current ChatGPT session, so private attachment is not complete.

## Other remaining read-only reconciliation

Before or independently of tunnel activation, safe read-only work remains:

- classify the four preserved unknown artifacts and one filesystem anomaly from the accepted security-boundary inventory using metadata/hash/path relationships only;
- rerun the executable Control Surfaces live inventory and retain its manifest/summary;
- rerun the corrected Asterisk warning audit and retain its final warning/failure summary.

None of those read-only tasks authorizes listener, firewall, authentication, SIP, carrier, or alert-delivery changes.

## Completion condition

The permanent Operator is complete only when the verified loopback MCP service is reachable through the approved Secure MCP Tunnel/private ChatGPT transport, ChatGPT discovers the exact reviewed bounded tools, identity/health and approved diagnostics succeed with durable audit evidence, rollback/revocation is proven, and no secret or new public management exposure has been introduced.

## Operating rule

Routine repository work and read-only inspection continue under standing authorization. Credentials/secret material, irreversible/destructive changes, privileged network/security changes, live carrier/call/message behavior, and other explicit stop conditions remain gated.
