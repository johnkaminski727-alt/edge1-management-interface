---
name: business159-shell-operator
description: Safely inspect and operate the WW.CX Business159 cPanel/shared-host account through guarded SSH-backed MCP tools. Use for Business159 connectivity, bounded inspection, deployment dry-runs/applies, staged file workflows, or exceptional attended account-level shell execution while preserving host/principal verification, redaction, timeouts, output limits, least privilege, and shared-host boundaries.
---

# Business159 Shell Operator

Use `business159-live-shell`. Preserve the distinction between read-only inspection, approved bounded mutation, and attended raw shell.

1. Use `business159_connection_test` when connectivity or identity is uncertain.
2. Prefer the named `business159.*` status tools or `business159_inspect` for diagnosis.
3. Use `business159_deploy` for the existing WW.CX deployment mechanism; default to dry-run. Apply only when the active task authorizes deployment, the connector gate is enabled, the dedicated deploy checkout is clean, and the expected commit is known.
4. Use the `business159_fs_*` lifecycle for bounded public-root file changes. Inspect the diff before approval/apply and verify afterward.
5. Use `business159_exec` only when a specific authorized account-level task cannot be completed through narrower tools and the attended raw-shell gate is enabled.

Never assume root, sudo, systemd, host firewall, kernel/network administration, or unrestricted paths. Never request or expose credentials. Keep SSH host-key checking enabled. Treat timeout, output-limit, host mismatch, principal mismatch, nonzero exit, redaction, or unavailable dependency as an incomplete operation rather than success.
