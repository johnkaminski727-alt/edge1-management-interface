# Edge1 Public Summary Staging Runtime Register

Date: 2026-07-30  
Classification: internal security and publication-boundary record  
System: `edge1.ww.cx` / WW.CX Operations Center  
State: repository implementation; disabled and not deployed

## Objective

Prepare an auditable, fail-closed release-staging layer for the minimized public summary while preserving the existing live Apache route and public filesystem unchanged.

## Assets

| Asset | Function | Boundary |
| --- | --- | --- |
| `config/security/edge1-public-summary-staging-policy.json` | Exact disabled policy | `enabled:false`, `deployment_authorized:false`, `live_publication_authorized:false` |
| `schemas/wwcx-edge1-public-summary-staging-policy-v1.schema.json` | Machine-readable policy shape | Repository validation only |
| `server/edge1_public_summary_stager.py` | Build, validate, hash, and atomically select minimized releases | Writes only a non-public staging root when explicitly enabled |
| `deploy/systemd/wwcx-edge1-public-summary-stager.service` | Proposed hardened root-only oneshot | Not installed or started |
| `deploy/systemd/wwcx-edge1-public-summary-stager.timer` | Proposed 60-second schedule | Not installed or enabled |
| `deploy/apache/edge1-public-summary.conf.proposed` | Exact future anonymous minimized-route and header contract | Proposal only; no active Apache path |
| `tests/test_edge1_public_summary_stager.py` | Functional, privacy, permissions, unit, and boundary checks | Temporary directories only |
| `docs/security/edge1-public-summary-staging-runtime-20260730.md` | Architecture, preflight, activation, rollback, and safety record | Repository only |

## Activation state

```json
{
  "status": "design_only",
  "enabled": false,
  "deployment_authorized": false,
  "live_publication_authorized": false,
  "activation_requires_explicit_authorization": true
}
```

A disabled invocation returns `state: disabled`, `changed: false`, and creates no staging directory.

No installer or activation script is included.

## Approved inputs

```text
/var/www/edge1-status/security-operations.json
/var/www/edge1-status/network-defense/data/network-defense.json
/var/www/edge1-status/operations-health.json
```

These are sanitized snapshots already used by the minimized exporter. Raw EVE, topology, detailed incident, Git, communications, wallet, mining, report, and evidence sources are outside the runtime allowlist.

## Exact public release

```text
index.html
app.js
style.css
public/status.json
```

The runtime rejects unknown assets, symlinks, oversized files, invalid UTF-8, CSP drift, inline stylesheet requirements, noncanonical feed paths, and restricted feed/route tokens.

The public status document remains `wwcx.edge1-public-status.v1` and contains only bounded component states, counts, coarse freshness, maintenance notice, read-only state, and the no-traffic-change flag.

## Filesystem contract

```text
/var/lib/wwcx-public-summary/
  current -> releases/<release-id>
  releases/<release-id>/...
  metadata/<release-id>.json
```

| Path class | Mode |
| --- | --- |
| Staging and release directories | `0755` |
| Public release files | `0644` |
| Metadata directory | `0700` |
| Metadata files | `0600` |

Each release is built in a temporary directory, checked for its exact file set and modes, renamed into place, recorded with per-file SHA-256 values outside the public tree, and selected using an atomic symlink replacement.

Existing releases are not overwritten or pruned.

## Service sandbox

The proposed service requires:

- root execution and `UMask=0022`;
- strict systemd filesystem protection;
- read-only access to the repository and exact sanitized source files;
- write access only to `/var/lib/wwcx-public-summary`;
- empty capability sets;
- `AF_UNIX` only;
- no subprocess, network client, listener, Apache mutation, or public-tree write.

The proposed timer uses a 60-second interval and `Persistent=false`.

## Proposed public header boundary

```text
Cache-Control: no-store, max-age=0
Content-Security-Policy: default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
Access-Control-Allow-Origin: absent
Directory listing: disabled
```

The Apache proposal is not installed and cannot become active through this repository phase.

## Validation scope

The new tests are intended to prove:

- committed policy remains disabled and production paths are exact;
- route, header, runtime, and authorization drift is rejected;
- disabled operation performs no filesystem change;
- enabled temporary tests create only the exact release files;
- public files are `0644`, metadata is private, and SHA-256 values match;
- hostile source values do not propagate;
- existing releases are not overwritten;
- tampered or symlinked assets fail closed;
- runtime has no command, network, listener, systemctl, or Apache operation;
- systemd write scope excludes `/var/www`;
- Apache proposal has exact headers, no listing, no CORS, no proxying, and no authentication claim;
- no installer exists.

Exact-head workflow results and merge evidence remain pending until the pull request is validated.

## Live prerequisite status

A fresh authenticated Edge1 Apache, route, header, filesystem, service, and capacity inventory is still required before any staging activation or public cutover. No authenticated Edge1 execution path was available in the current repository-authoring session, so no live-state claim is made.

## Explicit non-authorization

This phase does not authorize or perform staging-root creation on Edge1, unit installation, timer enablement, service invocation, `/var/www` writes, Apache installation or reload, alias/header changes, authentication, certificate, listener, DNS, firewall, traffic changes, public cutover, detailed-artifact removal, release pruning, or data deletion.
