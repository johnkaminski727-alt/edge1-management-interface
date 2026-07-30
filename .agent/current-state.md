# Current State

Last verified: 2026-07-30 01:42 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Current implementation branch: `feature/nftables-aggregate-observability-20260730`  
Latest live closeout merge: `1ea802effb166ced18c3e1e4675419349aa647eb`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- The accepted collector run published 22 enriched alerts with ports, application protocol, SID/GID/revision, and flow ID.
- Spamhaus is directly accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban is accepted as `active_observed`; the service and local socket were healthy and all 7 reported jails were observed.
- DNS policy remains `not_staged`; DNS enforcement remains disabled.
- Traffic controls remain unchanged.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z/acceptance-summary.json
```

## Current nftables aggregate implementation

Objective:

Publish bounded general nftables topology and counter aggregates without changing the firewall or claiming packet enforcement.

Implemented assets:

- `server/nftables_live_state_verifier.py`;
- `server/network_defense_nftables_exporter.py`;
- `deploy/systemd/wwcx-nftables-live-state.service`;
- `deploy/systemd/wwcx-nftables-live-state.timer`;
- updated capability-free `deploy/systemd/wwcx-network-defense.service`;
- `deploy/install-nftables-live-state-observability.sh`;
- verifier, privacy, integration, stale-state, runtime-wiring, deployment-safety, and rollback tests;
- updated legacy Network Defense, Spamhaus, and Fail2ban validators;
- architecture document and implementation register.

Contract:

```text
wwcx.nftables-aggregate-live-state.v1
```

Private runtime snapshot after activation:

```text
/var/lib/bigbird-networking/nftables/live-state.json
```

The verifier executes only:

```text
nft -j list ruleset
systemctl show nftables.service ...
```

Published evidence is limited to numeric object, family, hook, policy, verdict, element, packet, and byte aggregates plus sanitized service/observation states. Names, addresses, prefixes, ports, interfaces, devices, set/map elements, rule expressions, comments, handles, priorities, jump targets, raw output, credentials, and private keys are excluded.

Truthful states are `ruleset_observed`, `partial`, `empty`, `not_installed`, and `unavailable`. Every state keeps `enforcement_verified: false` and `traffic_controls_changed: false`.

The observer runs as root with only `CAP_NET_ADMIN` and `AF_UNIX AF_NETLINK`. Network Defense remains capability-free and consumes the sanitized snapshot through the final layered exporter.

## Repository audit note

A one-byte placeholder was accidentally created on `main` by commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d` before the feature branch existed. It was removed immediately by `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a`. No runtime or production system was affected.

## Completion status

Repository implementation and documentation are complete on the feature branch. Exact-head CI, PR merge, and bounded Edge1 activation remain pending.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban jail/action, proxy, routing, Suricata rule, reputation-list, authentication-boundary, or traffic-control mutation is included. Full rulesets, rules, names, addresses, elements, packet payloads, raw logs, credentials, and private keys remain excluded.
