# Edge1 Agent Shell

Last updated: 2026-08-23

## Objective

Provide trusted WW.CX agents with a durable, persistent Edge1 administration surface that is genuinely capable of read/write/update/service/shell work through the existing private MCP tunnel instead of forcing every mutation into a manual paste-box workflow.

John explicitly requested that this surface be fully capable and stated that the current tunnel-connected Edge1 environment should not be artificially constrained by the previous read-only posture.

## Architecture decision

Keep the existing 16-tool read-only `edge1-operator-mcp` contract as the routine status/diagnostic surface.

Add a second high-authority MCP server:

```text
127.0.0.1:8114/mcp -> wwcx-edge1-agent-shell.service
```

The existing Secure MCP Tunnel configuration gains a second `agent-shell` channel while preserving the existing `main` channel at `127.0.0.1:8102/mcp`. Both use the existing loopback bearer boundary. No public listener, Apache route, DNS change or firewall opening is introduced.

## Intended production capability

`EDGE1_AGENT_SHELL_MODE=full` is the intended production mode.

The service unit runs as root. Full mode contains no per-service, per-command or per-directory allowlists. It exposes arbitrary shell execution plus typed file and systemd helpers. The operating-system process authority is the capability ceiling.

Typed file writes support optional SHA-256 preconditions so agents can use optimistic concurrency when editing important files, but the precondition is optional rather than an authorization gate.

## Tool contract

- edge1_agent_identity
- edge1_agent_capabilities
- edge1_agent_exec
- edge1_agent_file_stat
- edge1_agent_file_read
- edge1_agent_file_write
- edge1_agent_file_patch
- edge1_agent_file_manage
- edge1_agent_service

## Persistent evidence

Agent Shell calls write metadata-only JSONL audit events to `/var/log/wwcx-edge1-agent-shell/audit.jsonl`. Command text, stdin and file contents are not placed into the audit ledger. Arbitrary command output is redacted for common credential shapes by default; the trusted caller may request exact output when necessary.

## Deployment state

Source only until a write-capable Edge1 path performs the installer and tunnel reload.

The installer is dry-run by default and under `--apply` creates an immutable runtime copy under `/opt/edge1-agent-shell/releases/<commit>`, moves the `current` pointer atomically, preserves a `previous` pointer/backup, starts the root service, verifies full-mode health and proves port 8114 is loopback-only. Failed postflight attempts rollback to the previous runtime or disable the first install.

## Live acceptance

Do not claim live completion until all are observed after deployment:

1. `edge1-agent-shell.service` enabled/active as root.
2. `127.0.0.1:8114` only; no wildcard/public listener.
3. `/healthz` reports `mode=full`.
4. Secure MCP Tunnel remains healthy with both `main` and `agent-shell` channels.
5. A fresh agent session discovers the nine Agent Shell tools.
6. Identity/capabilities show Edge1 and full mode.
7. Harmless read/write/update canary succeeds and is rolled back.
8. A harmless service-control canary succeeds (status plus a reviewed restart/reload only where appropriate).
9. Audit entries correlate to the calls without storing secret payloads.
10. Existing read-only Operator tools continue to work.

## Boundary

This design intentionally broadens host mutation authority for the trusted Agent Shell. It does not itself authorize unrelated external side effects such as payments, contracts, public communications, emergency calling, DNS/certificate changes, or irreversible deletion when a task has its own separate approval boundary.
