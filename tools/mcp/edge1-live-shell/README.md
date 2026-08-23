# Edge1 Live Shell MCP Connector

An SSH-backed MCP sidecar for trusted WW.CX agent operations on Edge1. It is designed for the authenticated tunnel/SSH environment where agents may need to inspect, create, update, move, copy, remove, chmod, restart, reconcile, and execute commands instead of being limited to the canonical read-only Operator surface.

The hardened `edge1-operator-mcp.service` remains the normal low-risk production diagnostics interface. This sidecar is the explicit write-capable escalation/operator path.

## Design

The connector does **not** store SSH keys, tokens, passwords, tunnel identifiers, or private addresses in the repository. OpenSSH configuration and credentials stay outside the repo. SSH always uses `BatchMode=yes` and `StrictHostKeyChecking=yes`.

The tool surface is intentionally capable:

- structured filesystem read/write/update operations;
- atomic replacement with optional SHA-256 compare-and-swap;
- backup-first writes/moves/copies/removals by default;
- arbitrary POSIX shell execution when enabled;
- working-directory and stdin support;
- optional sudo shell/filesystem execution when enabled and permitted remotely;
- allowlisted service restarts;
- the existing commit-pinned Cookie Monster and Edge1 release transactions;
- bounded output, timeouts, and basic secret redaction.

Capability gates exist so the same binary can run in read-only or full-operator mode. They are deployment configuration, not source limitations.

## Requirements

- Node.js 20+
- OpenSSH client
- working SSH alias `edge1` configured outside the repository
- authenticated tunnel or equivalent trusted path to Edge1
- remote account with the permissions needed for the intended work
- optional non-interactive sudo policy for privileged work

## Install and test

```sh
cd tools/mcp/edge1-live-shell
npm install
npm run check
npx @modelcontextprotocol/inspector node src/index.js
```

Run `edge1_capabilities` and `edge1_connection_test` before the first mutation in a session.

## Trusted-tunnel full operator profile

For John's authenticated Edge1 tunnel environment, the intended full-capability profile is:

```text
EDGE1_SSH_ALIAS=edge1
EDGE1_ENABLE_FILE_MUTATIONS=1
EDGE1_ENABLE_RAW_SHELL=1
EDGE1_ALLOW_SUDO_SHELL=1
EDGE1_ALLOW_RESTARTS=1
EDGE1_ALLOW_COOKIE_MONSTER=1
EDGE1_ALLOW_RELEASES=1
EDGE1_COOKIE_MONSTER_TARGET_SHA=<reviewed-40-character-git-commit>
EDGE1_RELEASE_TARGET_SHA=<reviewed-40-character-git-commit>
EDGE1_ALLOWED_SERVICES=edge1-operations-api,edge1-operator-mcp,bigbird-ai-gateway
EDGE1_REPOSITORIES=edge1-interface=/opt/edge1-management-interface;bigbird-gateway=/opt/bigbird-ai-gateway
EDGE1_TIMEOUT_MS=30000
EDGE1_MAX_OUTPUT_BYTES=262144
EDGE1_MAX_FILE_BYTES=8388608
```

The SSH account and sudoers policy remain the final operating-system authority. `EDGE1_ALLOW_SUDO_SHELL=1` makes the MCP tools willing to request sudo; it does not bypass remote sudo policy.

## MCP tools

### `edge1_capabilities`

Reports the currently enabled profile so an agent can determine whether it has read-only, write, restart, release, or sudo authority.

### `edge1_connection_test`

Returns remote hostname, authenticated principal, UID, and kernel identity.

### `edge1_inspect`

Provides convenient overview/resources/service/repository inspection.

### `edge1_fs`

Structured filesystem operator with actions:

- `stat`
- `list`
- `read`
- `write`
- `append`
- `mkdir`
- `move`
- `copy`
- `remove`
- `chmod`

`stat`, `list`, and `read` are available whenever the SSH principal can perform them. Mutating actions require `EDGE1_ENABLE_FILE_MUTATIONS=1`.

Writes use a temporary file in the destination directory, fsync it, and atomically replace the target. Existing targets are backed up by default as `.agent-backup-<UTC timestamp>`. Callers can pass `expectedSha256` to refuse stale updates. Binary content is supported through base64 encoding. `sudo=true` requires `EDGE1_ALLOW_SUDO_SHELL=1` plus matching remote sudo authority.

Removal is intentionally available because this is a full operator surface; agents must still respect their task's destructive-action approval boundary.

### `edge1_exec`

Runs caller-supplied POSIX shell commands over authenticated SSH and supports:

- command strings up to the configured limit;
- optional `cwd`;
- stdin payloads;
- optional `sudo=true`.

Requires `EDGE1_ENABLE_RAW_SHELL=1`. `sudo=true` additionally requires `EDGE1_ALLOW_SUDO_SHELL=1` and a remote sudo rule that allows the command.

### `edge1_restart_service`

Restarts one service from `EDGE1_ALLOWED_SERVICES` with `sudo -n systemctl restart`. Requires `EDGE1_ALLOW_RESTARTS=1`.

### `edge1_cookie_monster`

Preserves the narrower fixed Cookie Monster lifecycle (`preflight`, `sync_sources`, `activate`, `rollback_last`) for repeatable deployment work. Mutations stay commit-pinned.

### `edge1_release`

Preserves the durable release-controller lifecycle (`status`, `reconcile`, `rollback_last`). Reconcile remains pinned to `EDGE1_RELEASE_TARGET_SHA` so full shell capability does not weaken deterministic release promotion.

## Agent operating model

Use the structured tools when they express the job cleanly, and use `edge1_exec` when the task genuinely needs general shell access. The sidecar is not a substitute for task-level judgment: credentials should not be printed, destructive actions still need the appropriate authorization, and meaningful changes should retain validation/evidence.

A typical agent flow is:

1. `edge1_capabilities`
2. `edge1_connection_test`
3. inspect current state
4. perform file/shell/service/release changes
5. validate health, listeners, repository state, and changed files
6. retain rollback/evidence

## ChatGPT / agent architecture

The expected topology is:

```text
Agent / ChatGPT
    -> authenticated MCP connector host
    -> edge1-live-shell MCP sidecar
    -> OpenSSH through the existing trusted tunnel
    -> Edge1
```

This gives agents a genuine remote operator rather than forcing every write-capable task through new one-off named tools. The canonical read-only Edge1 Operator can remain connected in parallel for routine diagnostics.
