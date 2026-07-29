# Current State

Last verified: 2026-07-29 17:21 UTC
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative live collector-enrichment merge: `21b87664355e5f83173a630f24276389a6dcbbf6`
Latest synchronized reporting fix: `bb293f15da214d600abae823e4db17680eac036c`

## Verified live security observability

- Network Defense observability is deployed on Edge1.
- Security Correlation is live and consumed by Network Defense.
- Security Operations, Correlation, and Network Defense acceptance passed through `edge1.ww.cx`.
- DNS policy remains `not_staged`.
- DNS enforcement remains disabled.
- Traffic controls remain unchanged.

Base evidence:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
```

Domain evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
```

## Verified Suricata drill-down, caching, normalization, and enrichment

- Alert cards are accessible mouse- and keyboard-operated expand/collapse controls.
- Expanded details are limited to sanitized allowlisted fields.
- Browser requests remain `cache: "no-store"`.
- Edge1 last-known-good caching distinguishes live data from stale fallback data.
- Security Operations schema is `2.0`.
- Public alert schema is `wwcx.suricata-alert.v1`.
- Alert classification and severity-to-risk normalization are active.
- The source-controlled Big Bird collector retains allowlisted ports, application protocol, SID/GID/revision, and flow identifiers.

Normalization evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
```

Collector-enrichment evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
```

Final live collector result:

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
- DNS enforcement disabled;
- `traffic_controls_changed: false`.

## Spamhaus live-state verifier implementation

The next bounded observability phase is implemented on branch:

```text
feature/spamhaus-live-state-verifier-20260729
```

Implemented assets:

- `server/spamhaus_live_state_verifier.py`;
- `deploy/systemd/wwcx-spamhaus-live-state.service`;
- `deploy/systemd/wwcx-spamhaus-live-state.timer`;
- `deploy/install-spamhaus-live-state-observability.sh`;
- Network Defense exporter and DNS-aware wrapper integration;
- updated Network Defense runtime ordering and UI wording;
- parser, privacy, read-command, runtime-wiring, and deployment-safety validation;
- architecture record and register.

The verifier reads only:

```text
nft -j list table inet bigbird_spamhaus
systemctl show bigbird-spamhaus-filter.service ...
systemctl is-active bigbird-spamhaus-filter.timer
systemctl is-enabled bigbird-spamhaus-filter.timer
```

It publishes only sanitized counts and booleans under contract:

```text
wwcx.spamhaus-live-state.v1
```

Network Defense changes the Spamhaus component from `feed_ready` to `active_verified` only when the complete table, set, hooked-rule, service-result, timer, freshness, and safety contract passes.

`CAP_NET_ADMIN` is confined to the dedicated verifier service because nftables read access requires it. `wwcx-network-defense.service` remains capability-free.

Live activation is pending PR merge. The planned command is:

```bash
sudo bash ./deploy/install-spamhaus-live-state-observability.sh
```

Expected evidence root:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/<timestamp>
```

## Completion status

The base Security observability, domain exposure, Suricata drill-down, last-known-good cache, normalized alert schema, source collector enrichment, downstream refresh, and live acceptance are complete.

The Spamhaus live-state verifier is implemented and awaiting exact-head CI, merge, and live Edge1 activation.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban, proxy, routing, Suricata rule, reputation-list, authentication-boundary, or traffic-control change was made by the completed phases or is included in the verifier implementation. Payloads, packet bodies, raw EVE events, set elements, full firewall rulesets, credentials, and private keys remain excluded. Historical alert retention remains separate future work.
