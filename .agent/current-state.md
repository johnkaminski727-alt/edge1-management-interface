# Current State

Last verified: 2026-07-30 09:05 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Latest implementation merge: `6b7991b1e37c327813199057c90cf2a9f834aa14`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- The accepted collector run published 22 enriched alerts with ports, application protocol, SID/GID/revision, and flow ID.
- Spamhaus is directly accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban is accepted as `active_observed`; the service and local socket were healthy and all 7 reported jails were observed.
- General nftables aggregate visibility is accepted as `ruleset_observed`.
- DNS policy remains `not_staged`; DNS enforcement remains disabled.
- Traffic controls remain unchanged.

## Accepted nftables aggregate live state

The read-only nftables observer implementation merged through PR #124 and was activated successfully on Edge1.

Exact accepted public result:

```json
{
  "nftables_state": "ruleset_observed",
  "nftables_observed": true,
  "nftables_enforcement_verified": false,
  "tables": 4,
  "chains": 14,
  "base_chains": 7,
  "rules": 46,
  "sets": 6,
  "maps": 0,
  "counter_packets": 1866364147,
  "counter_bytes": 4478865062835,
  "verified_enforcement_count": 1,
  "overall_state": "limited",
  "available_sources": 8,
  "source_count": 9,
  "dns_policy_state": "not_staged",
  "dns_enforcement_enabled": false,
  "traffic_controls_changed": false
}
```

The verifier snapshot immediately before the Network Defense refresh reported the same topology with counters of 1,866,363,293 packets and 4,478,862,225,755 bytes. The slightly higher public counters were observed moments later and reflect normal live counter movement; they are not a configuration difference.

General nftables remains `enforcement_verified: false` by design. Aggregate topology, verdict, and counter evidence does not independently prove policy correctness, intended enforcement, or that every packet path traverses a particular rule. The one verified enforcement source remains the dedicated Spamhaus contract.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z/acceptance-summary.json
```

## Complete evidence set

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
```

## Repository audit note

A one-byte placeholder was accidentally created on `main` by commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d` before the feature branch existed. It was removed immediately by `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a`. No runtime or production system was affected.

## Completion status

The bounded Security observability, Suricata enrichment, Spamhaus enforcement verification, Fail2ban health observability, and general nftables aggregate-observability phases are implemented, merged, deployed, and accepted.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban jail/action, proxy, routing, Suricata rule, reputation-list, authentication-boundary, or traffic-control mutation was made by these observability phases. Full rulesets, rule expressions, names, addresses, interfaces, elements, packet payloads, raw logs, credentials, and private keys remain excluded.
