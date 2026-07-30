# Current State

Last verified: 2026-07-30 19:08 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative closeout: `74323ce0d572806278afe400f3c1e9e244e89d10`  
Current design branch: `design/edge1-public-access-boundary-20260730`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- Spamhaus is accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban is accepted as `active_observed`; the service and local socket were healthy and all 7 reported jails were observed.
- General nftables aggregate visibility is accepted as `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls are unchanged.

## Completed repository phases

- Network Defense freshness: closed through PR #127 at `bbefaca8fddc33270178daada5ca20ca3fce0c08`; not claimed live.
- Protected Suricata retention design: closed through PR #129 at `74323ce0d572806278afe400f3c1e9e244e89d10`; policy remains disabled and no runtime exists.

## Current design phase — public access boundary

Repository evidence shows that `/edge1-status/` is a mixed boundary. The public-facing dashboard consumes detailed files containing host inventory, service names, kernel/runtime versions, interfaces/routes, WireGuard/resolver output, Git state and recent changes, timer schedules, incident detail/history, communications/carrier passthrough, wallet/mining state, and generated reports.

Design decision:

- do not retain the current mixed tree unchanged as the long-term boundary;
- keep a minimized public landing page and allowlist-only aggregate status feed;
- move detailed operations to a separately authenticated, fail-closed surface under a future exact authorization.

Design assets:

- `config/security/edge1-public-access-boundary-policy.json`;
- `schemas/wwcx-edge1-public-access-boundary-policy-v1.schema.json`;
- `docs/security/edge1-public-access-boundary-design-20260730.md`;
- `registers/edge1-public-access-boundary-design-register-20260730.md`;
- `tests/validate_edge1_public_access_boundary_design.py`.

The policy is `design_only`, `enabled: false`, and `deployment_authorized: false`.

## Target boundary

Future public outputs are limited to:

```text
/edge1-status/
/edge1-status/public/status.json
```

The public contract permits only bounded aggregate state, count, freshness, maintenance, read-only, and no-traffic-change fields. Detailed security, topology, change, automation, incident, communications, financial, and report data is classified restricted.

A future authenticated root is represented as `/edge1-ops/`, but the browser authentication model, proxy routing, scopes, and cutover require separate exact authorization.

## Current validation status

- Accepted domain record, publisher, dashboard dependencies, and representative exporters were inspected.
- A complete repository route-class policy and forbidden-field contract were added.
- Static validation was added.
- Live Apache authorization, headers, CORS, directory listing, aliases, and complete route matrix remain unverified because no authenticated Edge1 shell is available.
- No Apache, proxy, auth, certificate, DNS, listener, `/var/www`, service, or traffic change exists in this phase.

## Authoritative existing live evidence

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
```

## Safety boundary

This phase is design-only. It does not authorize or change DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation lists, authentication, certificates, listeners, public access, published files, deletion, or production traffic.
