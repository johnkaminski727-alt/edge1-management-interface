# WW.CX Edge1 Agent Shell Plugin

This workspace plugin routes trusted Edge1 administration requests to the high-authority Agent Shell MCP tools introduced by PR #535 while preserving the ordinary read-only Edge1 Operator for routine status/diagnostics.

## Package identity

- plugin: `wwcx-edge1-agent-shell`
- display: `WW.CX Edge1 Agent Shell`
- packaged Skill: `wwcx-edge1-agent-shell-router`
- app dependency alias: `edge1`
- app ID: the existing WW.CX Edge1 workspace app

The package intentionally has a distinct plugin/Skill identity from `WW.CX Edge1 Live Operator`, avoiding the earlier app-generated-plugin naming collision.

## Expected live tool families

Ordinary read-only tools remain `edge1.*`.

The Agent Shell family is:

- `edge1_agent_identity`
- `edge1_agent_capabilities`
- `edge1_agent_exec`
- `edge1_agent_file_stat`
- `edge1_agent_file_read`
- `edge1_agent_file_write`
- `edge1_agent_file_patch`
- `edge1_agent_file_manage`
- `edge1_agent_service`

The plugin does not manufacture those tools. They must be discovered from the live Edge1 app after `edge1-agent-shell.service` and the Secure MCP Tunnel `agent-shell` channel are actually deployed.

## Intended UX

A user or trusted agent should be able to say things such as:

- “Update this Edge1 config and restart the affected service.”
- “Deploy the current reviewed release to Edge1 and verify it.”
- “Fix the stale checkout and prove the running services use the new release.”
- “Read, edit, or replace this file on Edge1.”

The router should select the live Agent Shell tools without requiring the user to think about SSH commands, MCP names, or a manual paste-box workflow.

## Live acceptance gate

Source validation is not live acceptance. After the host service/tunnel channel exists:

1. upload/install this distinct plugin package in the WW.CX workspace;
2. verify its detail page shows `WW.CX Edge1 Agent Shell`, the packaged router Skill, and the Edge1 app dependency;
3. start a fresh normal agent/chat session;
4. request `edge1_agent_capabilities` semantically (for example: “What full Agent Shell capabilities are live on Edge1?”);
5. pass only if a real live response reports `mode=full` and the expected tool family is exposed;
6. perform a harmless write/update/rollback canary and verify the audit ledger;
7. confirm ordinary `edge1.health` still works afterward.

If the existing Edge1 app does not aggregate the tunnel's second MCP channel, create a distinct workspace app for the Agent Shell and change only `.app.json` to that new app ID. Do not fake tool discovery or silently fall back to repository documentation.
