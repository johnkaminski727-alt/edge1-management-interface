# Edge1 Secure MCP preactivation compatibility acceptance — 2026-08-20

Status: **READ-ONLY COMPATIBILITY GATE PASSED**. Tunnel activation remains separately explicit and is not authorized by this record.

## Context

The global systemd unit-directory trust boundary was repaired and verified first. The authenticated human operator then reran the hardened Secure MCP compatibility validator from the reviewed production checkout `d26b9f3e625f70c5aa5a9d29342a2537218f0f46` on `edge1.ww.cx` as `wwadmin`.

No tunnel start/stop/restart/reload/enable/disable command was run.

## Accepted pre-state

```text
/etc/systemd/system owner=root:root mode=0755
/etc/systemd/system/edge1-secure-mcp-tunnel.service owner=root:root mode=0644
edge1_operator_tunnel_unit_readable=yes
edge1-secure-mcp-tunnel active=inactive enabled=disabled
edge1-operator-mcp active=active enabled=enabled
bigbird-ai-tunnel active=active enabled=enabled
```

## Hardened validator result

```text
tunnel_client_version=0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144 (git sha: 105e17a79a36e4e5c897fd698ed2b8dbf935b144)
tunnel_client_sha256=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100
launcher_sha256=c0b7788bc40c3668b75b6f6410885bd9ce89a39e08c962b80a2e86f4497868f4
config_sha256=370c00ebb6a7a82d27137feb7a30beb6b881d8482c6ec950faf73cf42187b566
service_unit_sha256=a79a7ae19b2fb639c34a895c36b3ef3055a83b2342e037ddf60546cdda4d77dd
unauthenticated_mcp_http=401
authenticated_mcp_http=405
oauth_path_candidate_http=404
oauth_root_candidate_http=404
raw_doctor_rc=2
compatibility_override=known_0.0.10_optional_oauth_metadata_false_negative
EDGE1_TUNNEL_COMPAT_DOCTOR=PASS
validator_rc=0
```

The accepted compatibility override is limited to the already-reviewed tunnel-client `0.0.10` optional OAuth-metadata false negative. It does not waive any binary hash, asset hash, bearer-boundary, service-state, or endpoint-result check.

## Post-state equivalence

```text
edge1-secure-mcp-tunnel active=inactive enabled=disabled
edge1-operator-mcp active=active enabled=enabled
bigbird-ai-tunnel active=active enabled=enabled
EDGE1_SECURE_MCP_COMPATIBILITY=PASS
compat_wrapper_rc=0
```

The pre/post service state was equivalent. No tunnel activation was requested or performed.

## Remaining preactivation work

Before any attended tunnel start, complete the remaining read-only closeout work:

1. classify the four preserved unknown security-inventory records plus one filesystem anomaly using metadata/hash/path/relationship evidence only and record the exact protected inventory evidence directory;
2. rerun the executable Control Surfaces inventory and retain its manifest/summary;
3. rerun the corrected Asterisk warning audit and retain the final warning/failure summary.

Only after those read-only items are reconciled may the workflow return to the separate explicit attended tunnel-activation approval boundary. Passing this compatibility gate is not authorization to start or enable `edge1-secure-mcp-tunnel.service`.
