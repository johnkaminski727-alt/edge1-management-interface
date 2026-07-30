# Current State

Last verified: 2026-07-30 19:28 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative closeout: `1d995bbc0ec9029c9853d9968470f248eb8b6995`  
Current feature branch: `feature/edge1-minimized-public-summary-20260730`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Suricata drill-down, caching, normalization, and source enrichment are live.
- Spamhaus is `active_verified`; Fail2ban is `active_observed`; nftables is `ruleset_observed`.
- Network Defense remains `limited`, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls are unchanged.

## Completed repository phases

- Network Defense freshness closed through PR #127; live activation unclaimed.
- Protected Suricata retention design closed through PR #129; disabled and non-deploying.
- Public access-boundary design closed through PR #131 at `1d995bbc0ec9029c9853d9968470f248eb8b6995`.

## Current repository phase — minimized public summary

Phase 1 is implemented without live routing or publication.

Assets:

- `server/edge1_public_status_exporter.py`;
- `schemas/wwcx-edge1-public-status-v1.schema.json`;
- `src/web/public-status/index.html`;
- `src/web/public-status/app.js`;
- hostile fixtures under `tests/fixtures/edge1_public_status/`;
- `tests/validate_edge1_public_status.py`;
- implementation documentation and register.

## Output contract

Schema identifier:

```text
wwcx.edge1-public-status.v1
```

The exporter emits only:

- schema version and generation time;
- overall state;
- three fixed category records: Security, Network Defense, Operations;
- bounded count and coarse freshness per category;
- an explicit capped maintenance notice;
- `read_only:true` and `traffic_controls_changed:false`.

It never copies source objects, detail strings, errors, paths, addresses, ports, IDs, service names, Git state, incidents, reports, communications, wallet, or mining detail.

## Build and publication boundary

- All three source paths are required CLI arguments.
- Default output is `build/edge1-public-status/status.json`.
- No `/var/www`, Apache, systemd, command execution, or network access exists in the exporter.
- The page fetches only `./status.json` and is not connected to a deploy path.
- No live status URL or public cutover is claimed.

## Validation status

- Exact field and state allowlists implemented.
- Hostile fixtures include internal values that must not propagate.
- Count, maintenance, freshness, stale, missing-source, atomic-output, page, and no-deployment validations added.
- Exact-head CI, scope review, mergeability, and merge remain pending.

## Live evidence gaps

No authenticated Edge1 shell is available. Apache routes, aliases, authorization, headers, CORS, directory listing, and actual filesystem exposure remain unverified.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation list, authentication, certificate, listener, public access, `/var/www` publication, deletion, or production traffic is changed.
