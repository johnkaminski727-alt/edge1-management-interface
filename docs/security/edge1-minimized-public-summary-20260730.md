# Minimized Edge1 Public Summary

Date: 2026-07-30  
System: `edge1.ww.cx` / WW.CX Operations Center  
Status: repository implementation only; not routed, published, deployed, or live

## Objective

Implement Phase 1 of the accepted public-boundary design without changing the current public tree.

The implementation provides:

- an explicit allowlist-only summary exporter;
- schema `wwcx.edge1-public-status.v1`;
- hostile fixtures containing internal topology, alert, Git, incident, service, and report detail;
- a static landing page that consumes only the minimized document;
- no deploy script, systemd unit, Apache configuration, `/var/www` output default, authentication change, or route change.

## Inputs

The exporter accepts three explicit JSON input paths:

- Security Operations snapshot;
- Network Defense snapshot;
- Operations Health snapshot.

The CLI has no default live input paths. All three inputs are required.

The exporter does not pass through source objects or arbitrary source strings. It reads only these bounded values:

- Security Operations: health state, recent-alert count, generation time;
- Network Defense: overall state, available-source count, generation time;
- Operations Health: overall state, check count, generation time.

Detailed source records, alerts, metrics, paths, errors, recommendations, names, identifiers, addresses, ports, and nested data are ignored.

## Output contract

Schema:

```text
schemas/wwcx-edge1-public-status-v1.schema.json
```

Schema identifier:

```text
wwcx.edge1-public-status.v1
```

Exact top-level fields:

```text
schema_version
generated_at
overall_state
component_category
maintenance_notice
read_only
traffic_controls_changed
```

`component_category` is a fixed three-record array in this order:

1. `security`;
2. `network_defense`;
3. `operations`.

Each record contains only:

```text
component_category
component_state
bounded_count
freshness_bucket
```

Allowed component states:

```text
healthy
limited
attention
unavailable
```

Allowed freshness buckets:

```text
fresh
aging
stale
unknown
```

The document always reports:

```json
{
  "read_only": true,
  "traffic_controls_changed": false
}
```

## Count limits

- Security recent-alert count: maximum 999;
- Network Defense available-source count: maximum 99;
- Operations check count: maximum 99.

Counts do not include item identities or descriptions.

## Freshness limits

- `fresh`: age at most five minutes;
- `aging`: more than five and at most fifteen minutes;
- `stale`: more than fifteen minutes;
- `unknown`: missing or invalid generation time.

A stale available component is represented as `attention`.

## Overall state

- `unavailable`: every component unavailable;
- `attention`: at least one component requires attention or is stale;
- `limited`: at least one component is limited or unavailable and none requires attention;
- `healthy`: all three components are healthy.

## Maintenance notice

The optional maintenance notice is supplied explicitly by the caller, whitespace-normalized, and capped at 160 characters. It is never derived from source error, recommendation, incident, or report text.

## Output path and publication boundary

Default output:

```text
build/edge1-public-status/status.json
```

The exporter contains no `/var/www` path and requires explicit source inputs. It performs an atomic mode-`0644` write to the selected build/test output.

A mode-`0644` repository build artifact is not a public deployment. A future live publisher, response headers, path, ownership, and rollback require a separate authorized phase.

## Static page

Repository source:

```text
src/web/public-status/index.html
src/web/public-status/app.js
```

The page:

- fetches only `./status.json`;
- omits credentials and referrer data;
- requests browser no-store behavior;
- allows only the three component categories and approved state/freshness values;
- provides no links to detailed Security, Network Defense, wallet, mining, incident, report, or operations surfaces;
- contains no deployment or publication mechanism.

The page includes a CSP meta policy for repository preview. Server-side CSP, no-store, nosniff, referrer, CORS, and directory controls remain mandatory acceptance items in a future live phase.

## Hostile fixture validation

Fixtures deliberately include:

- host and kernel values;
- service names;
- addresses and ports;
- alert signatures and IDs;
- WireGuard, routes, and resolver detail;
- branch, commit, and dirty state;
- incident history;
- report filenames;
- arbitrary error and recommendation strings.

Validation recursively rejects forbidden field names and verifies that hostile values do not appear anywhere in the minimized output.

## Failure behavior

Missing, unreadable, invalid, or non-object source documents become an `unavailable` component with count `0` and freshness `unknown`.

The public document does not expose source errors, paths, exception text, or missing-file names.

## Validation

Repository validation must prove:

- exact output and component field allowlists;
- policy and schema alignment;
- hostile values and forbidden keys excluded;
- state, count, notice, and freshness limits;
- missing/stale input degradation;
- atomic build-scoped output;
- no command execution, network access, live publication path, Apache marker, or systemd marker;
- page consumes only the minimized document;
- no deployment/service assets exist.

## Deployment boundary

This phase does not include:

- copying files to `/var/www`;
- Apache aliases, routes, headers, or reloads;
- public URL activation;
- authentication or proxy changes;
- systemd service or timer;
- live source-path defaults;
- removal of existing public artifacts.

Those remain separately authorized phases after read-only live boundary inventory.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation lists, authentication, certificates, listeners, public access, published files, deletion, or production traffic is changed.
