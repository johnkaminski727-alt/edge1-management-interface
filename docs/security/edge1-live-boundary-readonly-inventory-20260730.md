# Edge1 Live Boundary Read-Only Inventory Collector

Date: 2026-07-30  
System: `edge1.ww.cx` / WW.CX Operations Center  
State: repository implementation only; disabled and not executed

## Objective

Provide a bounded, auditable operator command for the fresh live inventory required before any public-summary staging, authenticated `/edge1-ops/` implementation, restricted release construction, public cutover, or detailed-artifact removal.

The collector produces one JSON document on standard output. It does not create an evidence directory or output file, change a configuration, install a package, alter a service, open a listener, change a route, modify authentication, or change traffic.

A future authenticated operator may redirect standard output into a protected evidence location under a separately authorized execution procedure.

## Repository assets

| Asset | Purpose | Live state |
| --- | --- | --- |
| `config/security/edge1-live-boundary-inventory-policy.json` | Exact disabled host, route, filesystem, command, limit, privacy, and acceptance contract | Disabled |
| `server/edge1_live_boundary_inventory.py` | Read-only collector and JSON renderer | Not executed on Edge1 |
| `tests/test_edge1_live_boundary_inventory.py` | Policy, filesystem, hash, symlink, privacy, header, command, and non-mutation tests | Repository validation only |
| `docs/security/edge1-live-boundary-readonly-inventory-20260730.md` | Operator, privacy, evidence, and safety design | Repository only |

No systemd unit, timer, installer, deployment wrapper, privilege escalation command, evidence writer, Apache file, authentication configuration, or route change is included.

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

The command defaults to policy validation and prints only a disabled design-status object.

Inventory execution requires all three authorization flags to be true in an approved policy copy, plus both command-line gates:

```text
--execute
--ack-read-only
```

Partial authorization is rejected. The committed policy cannot execute the inventory.

## Host and repository boundary

Approved hostnames:

```text
edge1
edge1.ww.cx
```

Approved repository:

```text
/opt/edge1-management-interface
```

Before collecting detailed evidence, the collector verifies that the runtime hostname or FQDN matches the approved host list.

Repository evidence includes only read-only Git commands:

```text
git rev-parse --show-toplevel
git rev-parse --verify HEAD
git branch --show-current
git status --porcelain=v1 --untracked-files=all
```

It does not fetch, pull, switch, reset, clean, commit, push, or inspect a remote URL.

## Filesystem inventory boundary

Recursively inventoried roots:

```text
/var/www/edge1-status
/var/lib/wwcx-public-summary
/var/lib/wwcx-edge1-ops
```

For each entry the collector records bounded metadata such as type, relative path, mode, owner, group, size, and modification time. Regular files within capacity limits receive a complete SHA-256 digest.

Safety rules:

- symlinks are recorded but never followed;
- directories are scanned deterministically;
- sockets, devices, FIFOs, and other special files are never opened;
- regular-file hashing is bounded by per-file, aggregate-byte, and file-count limits;
- access, stat, scan, and hash errors are reported without changing the source;
- no file is opened for writing;
- no mode or ownership is changed;
- no missing directory is created.

Committed limits:

| Limit | Value |
| --- | ---: |
| Maximum entries per root | 10,000 |
| Maximum aggregate regular-file bytes per root | 5 GiB |
| Maximum single hashed file | 512 MiB |

When a bound is exceeded, the inventory is marked incomplete. The collector does not silently claim completeness.

## Secret metadata boundary

The following paths are metadata-only:

```text
/etc/wwcx-edge1-ops
/etc/wwcx-edge1-ops/oidc.json
/etc/wwcx-edge1-ops/client-secret
```

The collector may record existence, file type, mode, ownership, size, and modification time. It does not read or hash their contents. Symlink targets are redacted for metadata-only paths.

The output explicitly records:

```text
secret_contents_read: false
raw_cookie_values_captured: false
raw_token_values_captured: false
raw_location_queries_captured: false
```

## Apache inventory boundary

Read-only Apache command evidence:

```text
apache2ctl -V
apache2ctl -M
apache2ctl -S
apache2ctl -t
apache2ctl -t -D DUMP_RUN_CFG
```

The collector also scans regular, non-symlink Apache `.conf` and `.load` files beneath `/etc/apache2` for an exact directive allowlist, including aliases, proxy routes, authentication type, authorization requirements, headers, options, redirects, and selected non-secret OIDC settings.

Unlisted directives are omitted. Secret, password, passphrase, private-key, and token directives are not part of the allowlist and are never intentionally emitted.

Apache configuration scanning is bounded by:

| Limit | Value |
| --- | ---: |
| Maximum configuration files | 2,000 |
| Maximum aggregate configuration bytes | 16 MiB |

Package evidence uses read-only `dpkg-query` for Apache and the preferred OIDC adapter package.

## Route inventory boundary

The policy defines 13 public and future restricted routes beneath:

```text
/edge1-status/
/edge1-ops/
```

Each route is probed from two read-only vantage points:

- local TLS loopback using `curl --resolve edge1.ww.cx:443:127.0.0.1`;
- the public network path for `edge1.ww.cx`.

Probes use `HEAD`, do not follow redirects, capture no response body, and have a ten-second timeout.

The parser retains only selected security and content headers. It records redirect scheme, authority, and path but does not retain redirect query strings or fragments. It records cookie names and security attributes but never cookie values. It records only the authentication scheme from `WWW-Authenticate`.

## Service, listener, package, and capacity boundary

The collector uses read-only commands to capture:

- selected unit `LoadState`, `ActiveState`, `SubState`, `UnitFileState`, `FragmentPath`, and `MainPID` through `systemctl show`;
- listening TCP and UDP sockets through `ss -H -lntup`;
- installed Apache/OIDC package state through `dpkg-query`;
- filesystem capacity through `statvfs`.

It does not start, stop, restart, reload, enable, disable, mask, unmask, or edit a unit. It does not bind a socket or change a listener.

## Command execution boundary

Only executable candidates under standard system command roots are accepted. Commands are constructed internally from fixed read-only argument sets. The policy exposes no arbitrary shell string or command-line override.

Every command:

- uses an absolute executable path;
- receives no standard input;
- runs without a shell;
- uses a fixed minimal environment;
- has a 20-second timeout;
- has separate one-MiB stdout and stderr bounds;
- reports return code, truncation, timeout, or command unavailability.

The collector itself does not use `sudo` or privilege escalation. A future operator must run it through the approved authenticated execution path with the minimum principal needed for complete read-only evidence.

## Output contract

Output is a single JSON object using:

```text
wwcx.edge1-live-boundary-inventory.v1
```

Major sections:

```text
identity
repository
apache
routes
filesystems
metadata_only_paths
units
listeners
capacity
```

Terminal safety fields:

```text
secret_contents_read: false
raw_cookie_values_captured: false
raw_token_values_captured: false
raw_location_queries_captured: false
output_file_written: false
mutation_performed: false
traffic_controls_changed: false
```

The collector never accepts an output-file argument. Protected evidence capture is intentionally delegated to the authenticated operator wrapper so location, permissions, hashing, and chain of custody can be controlled externally.

## Required future execution procedure

A later authenticated operator phase must:

1. verify the exact repository revision and clean `main`;
2. inspect the policy and collector diff against the accepted merge;
3. create an execution-specific policy copy without committing it;
4. set the three execution authorization flags only after exact user authorization;
5. run repository tests and syntax validation;
6. execute the collector through the approved authenticated path;
7. capture stdout directly into a newly created protected evidence directory;
8. record collector, policy, and output SHA-256 values;
9. set evidence directory and file modes explicitly;
10. inspect limitations and refuse completeness claims when any bound or error occurred;
11. compare repository-declared artifacts with the complete live inventory;
12. update registers with exact evidence paths and terminal results.

The execution policy copy must be destroyed or archived as controlled evidence after use; the committed policy remains disabled.

## Acceptance use

The collected evidence is a prerequisite, not authorization. It may support later decisions about:

- installing the public-summary stager;
- selecting and configuring an OIDC provider and Apache adapter;
- building an immutable restricted release;
- validating authenticated and unauthenticated route matrices;
- planning a public cutover;
- reconciling and eventually removing detailed anonymous artifacts.

None of those actions are performed by this collector.

## Rollback boundary

Repository validation and a stdout-only read operation do not require operational rollback. If a future wrapper creates an evidence directory, rollback consists only of preserving or securely handling that evidence according to the authorized evidence procedure. The collector does not create temporary files or operational state.

## Safety boundary

No live inventory was executed in this repository phase. No file, directory, hash register, package, service, timer, listener, Apache configuration, authentication setting, route, certificate, DNS record, firewall rule, traffic control, public artifact, restricted release, or production traffic was created, changed, removed, or authorized.
