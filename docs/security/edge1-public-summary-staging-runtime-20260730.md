# Edge1 Minimized Public Summary Staging Runtime

Date: 2026-07-30  
System: `edge1.ww.cx` / WW.CX Operations Center  
State: repository implementation; disabled, not installed, not staged on Edge1, and not published

## Objective

Prepare a fail-closed server-side release bundle for the accepted minimized public summary without writing to the current public tree, changing Apache, activating a timer, creating a listener, or exposing a route.

This phase creates a non-public staging design under:

```text
/var/lib/wwcx-public-summary
```

The committed policy remains disabled and live publication remains explicitly unauthorized.

## Assets

| Asset | Purpose | Live state |
| --- | --- | --- |
| `config/security/edge1-public-summary-staging-policy.json` | Exact routes, sources, files, headers, permissions, and authorization gates | Disabled |
| `schemas/wwcx-edge1-public-summary-staging-policy-v1.schema.json` | Machine-readable policy contract | Repository only |
| `server/edge1_public_summary_stager.py` | Builds and verifies immutable minimized release directories | Not run on Edge1 |
| `deploy/systemd/wwcx-edge1-public-summary-stager.service` | Proposed hardened root-only oneshot | Not installed |
| `deploy/systemd/wwcx-edge1-public-summary-stager.timer` | Proposed 60-second staging schedule | Not installed or enabled |
| `deploy/apache/edge1-public-summary.conf.proposed` | Exact future alias and response-header boundary | Proposal only; not installed |
| `tests/test_edge1_public_summary_stager.py` | Functional, privacy, filesystem, systemd, and Apache contract tests | Repository validation only |

No installer, activation script, Apache enablement command, daemon reload, or public cutover script is included.

## Authorization gates

The committed policy requires:

```json
{
  "status": "design_only",
  "enabled": false,
  "deployment_authorized": false,
  "live_publication_authorized": false,
  "activation_requires_explicit_authorization": true
}
```

The stager performs no filesystem change unless both `enabled` and `deployment_authorized` are true. The CLI exposes only a policy path; it does not expose arbitrary source or destination overrides.

Live publication is a separate boundary. Enabling staging does not authorize Apache installation, route replacement, removal of detailed files, or public access.

## Source boundary

Only three existing sanitized snapshots are approved:

```text
/var/www/edge1-status/security-operations.json
/var/www/edge1-status/network-defense/data/network-defense.json
/var/www/edge1-status/operations-health.json
```

The existing minimized exporter reads only bounded state, count, and generation-time values. The stager does not read raw Suricata EVE, incident reports, topology inventories, Git history, wallet/mining records, communications data, or generated reports.

Missing or invalid sources degrade the public component to `unavailable`; source paths, exception text, and internal values are not copied into the public output.

## Static asset boundary

The static source allowlist is exact:

```text
index.html
app.js
style.css
```

Before staging, the runtime verifies:

- each asset is a regular non-symlink file under the approved repository directory;
- each asset is at most 1 MiB and valid UTF-8;
- the page uses the exact approved CSP;
- no inline stylesheet or `unsafe-inline` dependency exists;
- the page fetches only `./public/status.json`;
- no restricted feed or detailed-operations route token appears in the public assets.

The complete release allowlist is exact:

```text
index.html
app.js
style.css
public/status.json
```

No metadata, logs, manifests, source snapshots, or internal records are placed inside the release tree.

## Filesystem and atomicity

Proposed layout:

```text
/var/lib/wwcx-public-summary/
├── current -> releases/<release-id>
├── releases/
│   └── <release-id>/
│       ├── index.html
│       ├── app.js
│       ├── style.css
│       └── public/status.json
└── metadata/
    └── <release-id>.json
```

Permissions:

- staging and release directories: `0755`;
- public files: `0644`;
- metadata directory: `0700`;
- metadata files: `0600`.

A release is built in a temporary directory, validated for its exact file set and modes, renamed into the immutable release directory, recorded with SHA-256 metadata outside the public tree, and then selected through an atomic `current` symlink replacement.

Existing releases are never overwritten or pruned. Operational data deletion is outside this phase.

## Runtime sandbox

The proposed oneshot:

- runs as root with `UMask=0022`;
- has empty capability and ambient-capability sets;
- allows only `AF_UNIX`;
- reads only the repository and the three approved sanitized snapshots;
- writes only `/var/lib/wwcx-public-summary`;
- uses strict systemd filesystem, device, kernel, namespace, process, and memory protections;
- opens no TCP or UDP listener;
- executes no subprocess or control-plane command.

The timer is proposed at 60-second intervals but is committed only. The disabled policy makes an accidental service invocation a truthful no-op.

## Proposed public boundary

The file below is intentionally named `.proposed` and starts with a do-not-install warning:

```text
deploy/apache/edge1-public-summary.conf.proposed
```

It defines the future route:

```text
/edge1-status/ -> /var/lib/wwcx-public-summary/current/
```

and requires:

- `Options -Indexes +FollowSymLinks`;
- `AllowOverride None`;
- exact `Cache-Control: no-store, max-age=0`;
- exact Content Security Policy;
- `Referrer-Policy: no-referrer`;
- `X-Content-Type-Options: nosniff`;
- no `Access-Control-Allow-Origin` header.

The proposal does not include authentication or proxying. It is only the minimized anonymous route. Detailed operations remain a separate authenticated-boundary program.

## Required live preflight before any staging or cutover

A future authenticated operator phase must re-run and preserve read-only evidence for:

- host identity, principal, clean `main`, and exact revision;
- Apache vhosts, aliases, modules, active includes, and configuration test;
- current `/edge1-status/` route matrix and response headers;
- current public filesystem inventory, ownership, modes, and SHA-256 hashes;
- availability of `mod_alias`, `mod_headers`, and `mod_mime`;
- current timer/service states;
- disk capacity under `/var/lib`;
- absence of an existing conflicting `/var/lib/wwcx-public-summary` tree.

The historical completion preflight evidence remains at:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
```

This repository phase does not claim that the historical inventory is a substitute for a fresh cutover preflight.

## Future staged activation sequence

Only after exact staging authorization:

1. verify the authenticated Edge1 path, host, principal, clean `main`, and required revision;
2. capture fresh read-only Apache, route, header, filesystem, service, and capacity evidence;
3. validate the repository and exact policy;
4. install only the stager unit and timer with backups and rollback evidence;
5. create the staging root with approved ownership and modes;
6. invoke one staging run and verify the exact assets, modes, SHA-256 metadata, minimized schema, and unchanged public routes;
7. leave the current `/edge1-status/` tree and Apache configuration untouched;
8. record terminal staging acceptance.

Public cutover remains a later exact-authorized action after the authenticated detailed-operations boundary is ready.

## Rollback boundary

Staging rollback may stop and disable the proposed timer, restore prior unit files, and remove only a newly created unreferenced temporary staging attempt when exact evidence proves it is safe. Existing releases, metadata, public files, operational data, and evidence are preserved by default.

Public cutover rollback must restore the previous Apache include and route mapping from protected backup, run the configuration test, reload only after validation, and verify both local and public route matrices. That procedure is not implemented or authorized here.

## Safety boundary

No Edge1 host mutation, `/var/www` write, Apache include, alias, header, reload, authentication change, certificate change, listener, DNS, firewall, traffic-control change, public route, detailed-artifact removal, release pruning, or production traffic change was performed or authorized.
