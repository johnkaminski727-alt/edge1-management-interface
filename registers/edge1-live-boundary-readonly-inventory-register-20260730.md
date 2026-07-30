# Edge1 Live Boundary Read-Only Inventory Register

Date: 2026-07-30  
Classification: internal security, access-boundary, and evidence-collection design record  
System: `edge1.ww.cx` / WW.CX Operations Center  
State: repository implementation; disabled and not executed

## Objective

Prepare a bounded stdout-only collector for the fresh authenticated Edge1 evidence required before any public-summary staging, authenticated restricted-route implementation, detailed-artifact migration, public cutover, or detailed-artifact removal.

## Assets

| Asset | Function | Boundary |
| --- | --- | --- |
| `config/security/edge1-live-boundary-inventory-policy.json` | Exact disabled host, path, route, command, limit, privacy, and acceptance policy | Execution flags false |
| `server/edge1_live_boundary_inventory.py` | Collect read-only host, repository, Apache, route, filesystem, SHA-256, unit, listener, package, and capacity evidence | JSON to stdout only |
| `tests/test_edge1_live_boundary_inventory.py` | Authorization, hashing, symlink, secret, Apache, route-header, command, and non-mutation tests | Temporary files and mocks only |
| `docs/security/edge1-live-boundary-readonly-inventory-20260730.md` | Operator execution, privacy, evidence, and safety design | Repository only |

## Committed authorization state

```json
{
  "status": "design_only",
  "enabled": false,
  "execution_authorized": false,
  "acceptance": {
    "live_execution_authorized": false,
    "mutation_performed": false,
    "traffic_controls_changed": false
  }
}
```

The committed policy cannot execute the inventory. Partial authorization is rejected.

Runtime execution additionally requires:

```text
--execute
--ack-read-only
```

## Evidence scope

### Host and repository

- hostname, FQDN, effective user and group, platform, Python version;
- repository root metadata;
- Git top-level, exact HEAD, current branch, and porcelain status.

### Apache and authentication adapter

- Apache version, loaded modules, vhosts, configuration test, and runtime configuration dump;
- allowlisted directives from regular non-symlink Apache configuration files;
- Apache and `libapache2-mod-auth-openidc` package state.

### Routes

- 13 `/edge1-status/` and `/edge1-ops/` routes;
- local TLS loopback and public-network vantage points;
- `HEAD` only, no redirect following, no response bodies;
- allowlisted response headers;
- redirect query and fragment redaction;
- cookie-name and security-attribute metadata without cookie values;
- authentication scheme without challenge details.

### Filesystems and hashes

Recursively inventoried:

```text
/var/www/edge1-status
/var/lib/wwcx-public-summary
/var/lib/wwcx-edge1-ops
```

Regular files are SHA-256 hashed within explicit file-count, aggregate-byte, and per-file bounds. Symlinks are recorded and never followed. Special files are never opened.

Metadata only:

```text
/etc/wwcx-edge1-ops
/etc/wwcx-edge1-ops/oidc.json
/etc/wwcx-edge1-ops/client-secret
```

Secret contents and hashes are not read. Metadata-only symlink targets are redacted.

### Services, listeners, and capacity

- selected unit state through `systemctl show` only;
- listener state through `ss -H -lntup`;
- filesystem capacity through `statvfs`.

## Command boundary

Commands are internally constructed from an exact command-key allowlist and absolute executable candidates. They run without a shell, receive no standard input, use a fixed minimal environment, have bounded time and output, and report nonzero, timeout, unavailable, and truncation states.

No arbitrary shell string or output path is accepted.

## Output and privacy boundary

The collector emits one JSON document to stdout and records:

```text
secret_contents_read: false
raw_cookie_values_captured: false
raw_token_values_captured: false
raw_location_queries_captured: false
output_file_written: false
mutation_performed: false
traffic_controls_changed: false
```

The collector never writes an evidence file. A future authenticated wrapper must control evidence destination, permissions, hashes, and chain of custody.

## Bounded collection limits

| Limit | Value |
| --- | ---: |
| Command timeout | 20 seconds |
| Command stdout/stderr each | 1 MiB |
| Files per root | 10,000 |
| Aggregate regular-file bytes per root | 5 GiB |
| Single hashed file | 512 MiB |
| Apache configuration files | 2,000 |
| Apache configuration bytes | 16 MiB |

Any exceeded bound or read error marks the relevant section incomplete. Completeness must not be inferred from partial output.

## Validation scope

Repository tests are intended to prove:

- committed policy remains disabled, stdout-only, and non-mutating;
- partial authorization and weakened host, path, route, command, privacy, symlink, mutation, or traffic gates are rejected;
- complete authorization is structurally required before execution;
- regular files are hashed and symlinks are not followed;
- file and aggregate limits produce truthful incomplete states without modifying files;
- metadata-only paths do not expose content, hashes, or symlink targets;
- Apache directives are allowlisted and secret/private-key directives are omitted;
- route parsing excludes cookie values and redirect query contents;
- route probes use bounded `HEAD` requests without redirect following or bodies;
- command names and output are bounded;
- no output-file interface or host-mutation operation exists.

Exact-head workflow and merge evidence remain pending.

## Live execution prerequisite

No live execution was performed in this repository phase.

A future run requires:

- an authenticated Edge1 execution path;
- exact user authorization for the read-only inventory;
- a temporary authorized policy copy;
- accepted repository revision and clean working tree;
- protected evidence destination and permissions;
- SHA-256 of the collector, policy, and output;
- review of every limitation before any completeness claim.

## Explicit non-authorization

This phase does not authorize or perform live inventory, evidence-directory creation, source mutation, package installation, service or timer changes, listener changes, Apache changes, authentication changes, route changes, certificate, DNS, firewall, traffic changes, public-summary staging, restricted release creation, public cutover, detailed-artifact removal, pruning, or deletion.
