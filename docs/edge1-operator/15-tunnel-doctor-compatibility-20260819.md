# Edge1 Secure MCP Tunnel doctor compatibility — 2026-08-19

Status: host prerequisites verified; raw installed doctor has one reviewed false negative; attended tunnel activation remains separately gated.

## Host evidence

Authenticated read-only inspection on `edge1.ww.cx` verified:

- repository checkout reached merged PR #450 state on clean `main`;
- `/usr/local/bin/tunnel-client` version `0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144`;
- tunnel-client SHA-256 `937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100`;
- `/etc/edge1-tunnel/tunnel-id` present, `root:edge1-operator`, mode `0640`, readable by `edge1-operator` without displaying its value;
- `/etc/edge1-tunnel/runtime-api-key` present, `root:edge1-operator`, mode `0640`, readable by `edge1-operator` without displaying its value;
- `/etc/edge1-operator/mcp-token` present, `edge1-operator:edge1-operator`, mode `0600`, readable by `edge1-operator` without displaying its value;
- `edge1-operator-mcp.service` active/enabled;
- Edge1 MCP listener remains loopback-only on `127.0.0.1:8102`;
- `edge1-secure-mcp-tunnel.service` remained disabled/inactive before and after doctor;
- `bigbird-ai-tunnel.service` remained active/enabled.

No tunnel service start/enable command was run during this evidence capture.

## Raw doctor result

The staged launcher was run as `edge1-operator`:

```sh
/usr/local/libexec/edge1-tunnel/edge1-secure-mcp-tunnel.sh doctor
```

The installed 0.0.10 build passed every prerequisite except one:

```text
FAILED_CHECKS oauth_metadata
HTTP 404 from http://127.0.0.1:8102/.well-known/oauth-protected-resource/mcp
```

It returned exit code `2`. The service remained disabled/inactive.

This is not evidence that the Edge1 MCP bearer boundary is broken. The same doctor reported the MCP target reachable at `http://127.0.0.1:8102/mcp`, while the accepted Edge1 design intentionally authenticates tunnel runtime and discovery traffic with the static `Authorization` header configured in `mcp.extra_headers` and `mcp.discovery_extra_headers`.

## Upstream compatibility finding

The exact installed upstream source (`openai/tunnel-client` commit `105e17a79a36e4e5c897fd698ed2b8dbf935b144`) unconditionally runs an OAuth metadata check for every HTTP MCP target and marks a non-2xx protected-resource metadata response as failure. Its doctor probe does not apply the configured MCP static headers.

Later upstream source changes this behavior: when an HTTP MCP server simply does not advertise OAuth protected-resource metadata and all derived discovery candidates return HTTP 404, `oauth_metadata` is a passing optional-discovery case. Upstream describes this as appropriate for plain MCP servers that do not rely on OAuth/DCR/PRMD.

The Edge1 Operator does not rely on DCR/PRMD. It already has a private loopback bearer-authentication boundary, and the tunnel config supplies that bearer header to both runtime and discovery/probe traffic. Therefore adding synthetic OAuth metadata endpoints merely to satisfy the older doctor would misrepresent the authentication design and is not approved.

Likewise, the shared `/usr/local/bin/tunnel-client` must not be replaced merely to clear this doctor result because the same binary is already used by the accepted active Big Bird tunnel.

## Compatibility gate

Repository script:

```text
deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh
```

The validator is deliberately fail-closed. It accepts the reviewed old-doctor result only when all of the following are true:

1. it runs as `edge1-operator`;
2. the exact reviewed tunnel-client version and SHA-256 are present;
3. the installed launcher, tunnel config, and systemd service unit match their reviewed SHA-256 values;
4. tunnel-client, launcher, config, unit, tunnel ID, runtime API key, and MCP token retain their reviewed owner/mode metadata;
5. unauthenticated `GET /mcp` remains HTTP 401;
6. authenticated `GET /mcp` remains HTTP 405, proving the bearer credential is accepted by the POST-only transport without exposing it;
7. both OAuth protected-resource metadata candidates remain HTTP 404;
8. raw doctor exits exactly `2`;
9. the only failed check is exactly `oauth_metadata`;
10. the failure is the reviewed path-specific HTTP 404.

Because this validator is pinned to the exact old client build, an unexpected raw-doctor success is treated as environment/authentication drift and fails closed for re-review rather than bypassing the independent checks. A different tunnel-client version or SHA also fails closed before doctor is invoked. Any future tunnel-client upgrade requires a separate review and deliberate update of the version/SHA pin and expected doctor behavior.

Any different failed check, status, target, file hash, file metadata, or authentication behavior also fails closed.

## Staging installer safety

`deploy/edge1-tunnel/install-edge1-secure-mcp-tunnel.sh --apply` is a staging operation, not a redeploy or recovery operation. It must refuse to proceed if `edge1-secure-mcp-tunnel.service` is already active or enabled. It must never stop or disable an accepted tunnel merely because staging is rerun later.

## Next boundary

Run the compatibility validator read-only as `edge1-operator`. If it passes, the next step is attended activation of `edge1-secure-mcp-tunnel.service` without persistence, followed immediately by listener/service equivalence, local `/healthz`/`/readyz`, ChatGPT tunnel discovery, exact tool-contract validation, identity/health calls, audit evidence, and rollback checks.

Starting the tunnel is an account-linked production activation boundary. Do not enable persistence until attended acceptance succeeds. Do not change DNS, firewall, Apache, certificates, MCP bearer authentication, Big Bird tunnel configuration, SIP/carrier routing, or any public listener as part of this compatibility handling.
