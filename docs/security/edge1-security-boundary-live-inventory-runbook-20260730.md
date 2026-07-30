# Edge1 Security-Boundary Live Inventory Runbook

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Host: `edge1.ww.cx`  
Mode: authenticated, root-run, read-only host inventory

## Purpose

This bundle closes the evidence gap between the merged repository designs and any future live staging. It inventories the current anonymous detailed tree, Apache boundary, services, routes, listeners, candidate restricted/public roots, audit metadata, and storage capacity. It then reconciles the exact SHA-256 filesystem inventory against the merged restricted-artifact manifest.

It does not install, enable, start, stop, reload, route, authenticate, publish, copy, move, rename, chmod, chown, delete, prune, or alter traffic.

## Authorization

The exact user authorization is recorded without secret material in:

```text
config/security/edge1-security-completion-authorization-20260730.json
```

The inventory script verifies that read-only live inventory is authorized and that the immutable no-credential guardrail remains false before proceeding.

## Execution prerequisites

- authenticated access to `edge1.ww.cx`;
- root execution through the approved elevation path;
- clean `main` checkout at `/opt/edge1-management-interface`;
- Apache control command available;
- standard read-only inspection commands available;
- no credentials supplied in chat or command arguments.

## Execute

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
git status --short --branch
sudo bash tools/security/edge1-security-boundary-live-inventory.sh
```

Optional environment overrides are limited to repository, source-root, evidence-root, and HTTP origin paths. They do not enable mutations.

## Protected evidence

Each run creates a root-only directory under:

```text
/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory/<UTC timestamp>
```

Key outputs:

- host, principal, capacity, repository revision, and listener state;
- systemd state and redacted unit definitions for relevant publishers and proposed units;
- Apache syntax, vhosts, modules, config-file hashes, and directive-name-only readiness inventory;
- exact JSON filesystem inventory containing path, SHA-256, mode, and byte count;
- symlink and non-regular-file anomaly inventory;
- manifest reconciliation with mapped, unknown-preserved, and missing-known records;
- local and public anonymous route/status matrix;
- minimized header summary that never records cookie values;
- metadata-only candidate-root, audit-log, and retention-tree inventories;
- aggregate fail-closed result and SHA-256 evidence manifest.

## Secret-minimization boundary

- No password, client secret, token, cookie value, private key, environment dump, SSH material, shadow data, or authentication-file contents are collected.
- Systemd and HTTP text passes through `redact-edge1-boundary-text.py`.
- Apache directive values are never recorded; only directive names, file paths, and line numbers are captured.
- Apache configuration files are hashed for equivalence but are not copied into evidence.
- Audit logs are inventoried by metadata only; log contents are not read.

## Acceptance interpretation

The committed staging and cutover policies remain disabled. Therefore the inventory result must report:

```text
read_only_host_inventory=true
live_configuration_changed=false
source_tree_mutated=false
credentials_collected=false
staging_ready=false
cutover_ready=false
traffic_controls_changed=false
```

Unknown artifacts are preserved for review. Missing known artifacts are reported. Symlinks and non-regular files are anomalies. Any duplicate source or target mapping causes reconciliation to fail.

## Next gate

After a successful host run, the protected reconciliation must be reviewed before constructing a restricted release or changing authentication or routes. Provider/adapter selection must be based on the captured Apache/module evidence and must continue to keep credentials outside Git and chat.
