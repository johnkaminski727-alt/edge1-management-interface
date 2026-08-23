---
name: wwcx-edge1-agent-shell-router
description: Route trusted WW.CX Edge1 administration work to the full-capability private Agent Shell tools. Use when a request requires current Edge1 command execution, filesystem read/write/update, service control, deployment, repair, rollback, or another host mutation that the ordinary read-only Edge1 Operator cannot perform.
---

# WW.CX Edge1 Agent Shell Router

Use the live `edge1` app dependency for current Edge1 work. The ordinary `edge1.*` read-only tools remain the best source for routine health/status questions. Use the `edge1_agent_*` tools when the user's requested work actually requires host administration.

## Start with live state

For a consequential change, establish current identity/state before mutation. Prefer the ordinary bounded Edge1 Operator for broad snapshots when it is available, then use Agent Shell tools for the change itself.

Do not substitute repository documentation or remembered state for a live host check when live tools are available.

## Agent Shell tool routing

- Agent Shell identity -> `edge1_agent_identity`
- Capability/mode check -> `edge1_agent_capabilities`
- Arbitrary command execution, package tools, Git, process/network utilities, complex workflows -> `edge1_agent_exec`
- File metadata/hash -> `edge1_agent_file_stat`
- File content -> `edge1_agent_file_read`
- File create/replace/append/offset update -> `edge1_agent_file_write`
- Exact text update -> `edge1_agent_file_patch`
- Directory/file move/copy/remove/permissions/ownership/links -> `edge1_agent_file_manage`
- systemd status/start/stop/restart/reload/enable/disable/daemon-reload -> `edge1_agent_service`

## Full-mode operating model

The Agent Shell is intentionally a high-authority surface. When `edge1_agent_capabilities` reports `mode=full`, do not invent additional per-command, per-service, or per-directory approval gates merely because the tool is powerful. Execute the user's authorized engineering objective end to end.

Use the typed file and service tools when they make the operation clearer and easier to verify. Use `edge1_agent_exec` when the typed tools would make the task awkward or incomplete.

For important file updates, use the available SHA-256 precondition when practical:

1. stat/read the target;
2. preserve or record the prior state when rollback matters;
3. update with `expected_sha256`;
4. stat/read again to verify.

For deployments and service work, verify functional health after the command, not only exit status.

## Boundaries that still exist

Host authority is broad, but unrelated action authority does not magically expand. Continue to stop at genuinely separate boundaries such as credentials the user has not supplied/authorized, payments/contracts, destructive irreversible deletion without a verified target/rollback, public communications, emergency calling, number porting, or other materially separate external actions.

Do not print or commit private keys, passwords, bearer tokens, cookies, recovery codes, runtime API keys, or tunnel enrollment material. Use redacted output by default unless exact output is necessary to complete the task.

Do not open new public listeners, weaken authentication, disable host-key verification, or change DNS/firewall/certificates merely to work around a broken tool path unless the task itself explicitly calls for that change.

## Evidence and completion

For completed changes, capture enough live evidence to establish:

- what was changed;
- the relevant before/after identity or hash;
- service/process/listener health when applicable;
- rollback point or recovery method when applicable;
- that unrelated boundaries were not widened.

Do not claim an Agent Shell operation ran if the `edge1_agent_*` tools are not actually exposed in the current session. If the app exposes only the ordinary read-only `edge1.*` tools, report the Agent Shell as not yet live/discovered rather than pretending repository source is execution evidence.
