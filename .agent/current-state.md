# Current State

Last verified: 2026-07-29 16:57 UTC
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative implementation merge: `21b87664355e5f83173a630f24276389a6dcbbf6`

## Verified live security observability

- Network Defense observability is deployed on Edge1.
- Security Correlation is live and consumed by Network Defense.
- Security Operations, Correlation, and Network Defense acceptance passed through `edge1.ww.cx`.
- DNS policy remains `not_staged`.
- Enforcement remains disabled.
- Traffic controls remain unchanged.

Base evidence:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
```

Domain evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
```

## Verified Suricata drill-down, caching, and normalization

- Alert cards are accessible mouse- and keyboard-operated expand/collapse controls.
- Expanded details are limited to sanitized allowlisted fields.
- Browser requests remain `cache: "no-store"`.
- Edge1 last-known-good caching distinguishes live data from stale fallback data.
- Security Operations schema is `2.0`.
- Public alert schema is `wwcx.suricata-alert.v1`.
- Alert classification and severity-to-risk normalization are active.

Normalization evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
```

## Verified source collector enrichment

PR #115 moved the Big Bird operations collector into the authoritative Edge1 repository and added the allowlisted Suricata source contract.

- Implementation merge: `21b87664355e5f83173a630f24276389a6dcbbf6`.
- Authoritative source: `server/bigbird_ops_collect.py`.
- Runtime target: `/usr/local/libexec/bigbird-ops-collect.py`.
- Collector release: `edge1-suricata-enrichment-r1`.
- Source alert schema: `wwcx.suricata-source-alert.v1`.
- Existing `bigbird-ops-push.service` and 120-second timer remain in use.

Live activation passed with 22 alerts. Every observed alert supplied:

- source port;
- destination port;
- application protocol;
- signature ID;
- generator ID;
- revision;
- flow ID.

The public feed also verified all 22 alerts with those fields, while remaining bounded and sanitized.

Authoritative collector-enrichment evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
```

Nested normalization and observability evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation/observability-acceptance
```

Final live result:

- 22 alerts published;
- 22 alerts classified;
- 22 alerts assigned a known risk;
- 22 alerts with source and destination ports;
- 22 alerts with application protocol;
- 22 alerts with SID, GID, revision, and flow ID;
- cache mode `live`;
- cache stale `false`;
- Security Correlation refreshed with 22 events and 0 correlations;
- Network Defense state `limited`;
- DNS policy `not_staged`;
- enforcement disabled;
- `traffic_controls_changed: false`.

## Completion status

The bounded Security observability deployment, domain exposure, alert drill-down, last-known-good caching, normalized alert schema, source collector enrichment, downstream refresh, and live acceptance are complete.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban, proxy, routing, Suricata rule, reputation-filter, authentication-boundary, or traffic-control change was made. Payloads, packet bodies, raw EVE events, credentials, private keys, and arbitrary metadata remain excluded. Historical alert retention remains separate future work.