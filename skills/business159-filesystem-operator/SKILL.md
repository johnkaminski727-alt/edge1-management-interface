---
name: business159-filesystem-operator
description: Operate the staged Business159 public-root filesystem controller through bounded MCP tools. Use when asked to stage, inspect, diff, approve, apply, verify, audit, or roll back a small WW.CX file change on Business159 while enforcing relative-path scope, secret rejection, backup, checksum verification, file-level atomic replacement, and rollback semantics.
---

# Business159 Filesystem Operator

Use only the `business159_fs_*` tools from `business159-live-shell` for controlled file mutation.

Required lifecycle:

`stage -> status -> diff -> approve -> apply -> verify -> audit`

Use rollback when verification fails, when the user requests rollback, or after an authorized disposable smoke test.

Enforce the connector's scope below the configured Business159 public root. Never convert this workflow into arbitrary-path writes. Reject credentials, keys, tokens, cookies, sessions, `.env`/authentication material, database files, logs, backups, and unrelated customer/private data.

Before apply, confirm the stage ID, target relative path, candidate checksum, diff, and approval state. After apply, confirm the returned target checksum/mode and run the narrowest applicable web/PHP check when the changed file can affect application behavior.

For rollback, use only the stage-local backup or the stage-created-file marker. Do not manually delete or overwrite unrelated files to recover from a failed stage.

If `BUSINESS159_ALLOW_FILESYSTEM` is disabled or the live connector is unavailable, report the workflow as blocked rather than preparing an unbounded shell substitute.
