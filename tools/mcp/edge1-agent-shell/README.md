# WW.CX Edge1 Agent Shell

A full-capability MCP administration surface for trusted WW.CX agents operating Edge1 through the existing private Secure MCP Tunnel.

This is intentionally different from the ordinary read-only `edge1-operator-mcp` contract. The ordinary Operator remains the default diagnostic surface. The Agent Shell exists for work that actually requires host mutation and should be attached only to trusted workspace agents/operators.

## Design

```text
Trusted ChatGPT / Agent
        |
WW.CX private Secure MCP Tunnel
        |
127.0.0.1:8114/mcp
        |
wwcx-edge1-agent-shell.service
        |
Edge1 local OS
```

The Agent Shell runs locally on Edge1. It does not require a public SSH listener or a new external firewall rule. It reuses the private tunnel transport and may reuse the existing Edge1 MCP bearer token at the loopback hop.

The service is intended to run with the operating-system authority necessary for full administration. In the proposed production unit that means `User=root`. That is deliberate: the tunnel + bearer boundary is the authorization boundary, not a maze of per-command allowlists.

## Tool surface

- `edge1_agent_identity` — host/process identity.
- `edge1_agent_capabilities` — active mode, limits and endpoint.
- `edge1_agent_exec` — arbitrary `/bin/sh -lc` execution, optional cwd/stdin/environment, configurable timeout/output cap.
- `edge1_agent_file_stat` — metadata and SHA-256.
- `edge1_agent_file_read` — bounded UTF-8 or base64 reads with offset/length.
- `edge1_agent_file_write` — create, atomic replace, append, or offset writes; optional SHA-256 precondition.
- `edge1_agent_file_patch` — exact text replacement with optional SHA-256 precondition and atomic replacement.
- `edge1_agent_file_manage` — mkdir/remove/move/copy/chmod/chown/symlink/hardlink without path allowlists.
- `edge1_agent_service` — status/start/stop/restart/reload/enable/disable/daemon-reload for any syntactically valid systemd unit.

`edge1_agent_exec` is the final escape hatch: if Linux can do it and the Agent Shell process can do it, the tool can do it. The typed file and service tools exist to make routine agent work less error-prone, not to reduce authority.

## Capability modes

`EDGE1_AGENT_SHELL_MODE=full` is the intended trusted-tunnel mode and the package default.

`EDGE1_AGENT_SHELL_MODE=read-only` can be used for diagnostics or commissioning. In that mode file reads/stat and identity/capability queries remain available, while shell execution, file mutation and service mutation fail closed. Service `status` remains readable.

There are no per-service, per-directory or per-command allowlists in full mode.

## HTTP / tunnel boundary

The MCP endpoint binds only to loopback and requires a bearer token:

```text
EDGE1_AGENT_SHELL_HOST=127.0.0.1
EDGE1_AGENT_SHELL_PORT=8114
EDGE1_AGENT_SHELL_PATH=/mcp
EDGE1_AGENT_SHELL_TOKEN_FILE=/etc/edge1-operator/mcp-token
```

`/healthz` is a minimal loopback health endpoint. `/mcp` rejects requests without the bearer token. If an `Origin` header is present it must appear in `EDGE1_AGENT_SHELL_ALLOWED_ORIGINS`; an empty allowlist therefore rejects browser-originated MCP requests while still allowing the server-side tunnel client, which does not need a browser Origin.

No public listener, DNS record, Apache proxy or firewall opening is part of this design.

## Audit

Every tool call attempts to append a metadata-only JSONL audit record to:

```text
/var/log/wwcx-edge1-agent-shell/audit.jsonl
```

Audit records contain request ID, tool, timestamp, mode and bounded metadata such as path, action, command SHA-256, exit code and timeout state. File contents, stdin, command text and bearer tokens are not written to the audit log.

`edge1_agent_exec` output is redacted by default for common credential-shaped material. A trusted caller may set `redact_output=false` when exact output is genuinely required; the audit record still stores only the command hash, not command text or output.

## File-update semantics

For routine configuration editing, prefer the typed file tools over shell redirection:

1. `edge1_agent_file_stat` to capture current SHA-256.
2. `edge1_agent_file_read` to inspect the intended region.
3. `edge1_agent_file_write` or `edge1_agent_file_patch` with `expected_sha256`.
4. `edge1_agent_file_stat` again to verify the new identity.

`replace` and `patch` write a temporary file in the same directory, fsync it, and rename it into place. `expected_sha256` prevents an agent from overwriting a file that changed after inspection.

Large/binary data can be transferred in base64 chunks using `file_read` and `file_write` (`write_at`), or with normal shell tools through `edge1_agent_exec`.

## Why this is separate from the normal Operator

The existing production Edge1 Operator is useful precisely because its ordinary health/status contract is narrow and predictable. Turning every status request into implicit root authority would make routine observability harder to reason about.

The Agent Shell is therefore a second, explicitly high-authority surface carried by the same private transport. Agents can use the ordinary Operator for monitoring and the Agent Shell when the requested work actually needs read/write/update/service/shell authority.

## Deployment intent

The repository includes a root-run loopback systemd unit and installer under `deploy/edge1-agent-shell/`. The installer is dry-run by default, preserves the previous unit/runtime pointer, installs an immutable package copy, starts the service only under `--apply`, verifies `/healthz`, and leaves the existing read-only Operator untouched.

Tunnel wiring is a separate reviewed source change: add `http://127.0.0.1:8114/mcp` as an additional MCP server channel while preserving the existing `127.0.0.1:8102/mcp` channel and Authorization header.

Live activation is not proven by repository merge. Acceptance requires an authenticated deployment, tunnel tool discovery from a fresh agent session, a harmless read/write/rollback canary, service-control canary, audit verification, and proof that 8114 remains loopback-only.
