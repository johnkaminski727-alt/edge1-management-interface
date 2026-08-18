# Edge1 Control Surfaces live inventory

Date: 2026-08-18
Status: read-only activation preflight; no live execution implied

## Purpose

`scripts/control-surfaces-live-inventory.sh` packages the fresh-host evidence gate required before any Control Surfaces exposure-reduction, Apache redirect, FreePBX proxy, firewall, listener, or service change.

The runner is deliberately read-only. It does not restart or reload services, alter nftables, change listener bindings, enable or disable Apache sites, write telephony configuration, originate calls or messages, pull/reset repositories, or read known credential-bearing configuration files.

## Evidence location

The script creates a timestamped private directory under:

```text
~/.local/state/edge1-control-surfaces/evidence/<UTC timestamp>/
```

It sets `umask 077`, records a manifest with per-command exit status and start time, sanitizes common secret-bearing HTTP/configuration fields, and writes SHA-256 hashes for the retained text evidence and manifest.

Raw temporary stdout/stderr files are removed only after the sanitized retained record has been created. The retained evidence directory must never be committed to Git.

## Inventory coverage

The fixed command set captures, where the command exists and the authenticated principal is permitted to read it:

- host identity, OS, disk, memory, interfaces and routes;
- TCP/UDP listeners and owning process names;
- running systemd services and selected non-secret unit state;
- Edge1 and BigBird AI repository branch/head/remote state at the documented `/opt` paths;
- Apache version, build, modules, vhost map, enabled-site symlinks and `configtest`;
- nftables ruleset;
- WireGuard runtime state without reading private-key files;
- resolver state and `/etc/resolv.conf`;
- Asterisk uptime, channels, PJSIP endpoints/transports/registrations, HTTP, AMI, ARI and RTP runtime settings;
- Kamailio version, uptime and process state;
- FreePBX `fwconsole status`;
- process names without command-line arguments;
- local same-host HTTP header behavior for the ordinary Edge1 root, FreePBX Administration and UCP;
- loopback reachability of the Operations API and BigBird AI health endpoint;
- local TLS handshake identity for `edge1.ww.cx`.

Some commands can legitimately return nonzero because a package, unit, CLI command, or restricted read privilege is absent. Those failures are evidence and do not cause the runner to mutate the host or silently substitute a different operation.

## Execution gate

Run this only through the approved authenticated Edge1 operator path after verifying the target host and principal. The expected live sequence is:

```text
1. verify host and principal
2. verify repository path and preserve any unrelated dirty work
3. run the read-only inventory
4. inspect the sanitized evidence and classify listeners
5. identify public infrastructure, SIP/media/peering and management dependencies
6. define backup and rollback for the first proposed change
7. only then perform an authorized bounded mutation
```

If the live checkout does not yet contain this script, do not force-reset or overwrite the checkout merely to obtain it. First inspect the repository state. Transfer or synchronize the reviewed script only through the approved authenticated operator workflow while preserving unrelated work.

## Safety contract

The corresponding `tests/test_control_surfaces_live_inventory.py` and GitHub Actions workflow enforce the repository-side safety contract. CI proves only that the runner has the expected fixed read-only command surface and secret-handling guardrails; it does not prove current production state or successful live execution.
