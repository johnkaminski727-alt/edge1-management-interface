# Security Observability and nftables Aggregate Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Latest implementation merge: `6b7991b1e37c327813199057c90cf2a9f834aa14`

## Completed live work

- Network Defense and Security Correlation deployed and accepted.
- `edge1.ww.cx` HTTPS status pages and JSON feeds accepted.
- Accessible Suricata drill-down, last-known-good cache, normalized schema, and source collector enrichment deployed.
- Spamhaus live-state accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban live-state accepted as `active_observed` with service/socket health and all 7 reported jails observed.
- General nftables aggregate live-state accepted as `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS remains unstaged, and traffic controls remain unchanged.

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Authoritative live evidence

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z/acceptance-summary.json
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z/acceptance-summary.json
```

## Final nftables aggregate state

```json
{
  "ok": true,
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

The observer snapshot immediately before the Network Defense refresh reported 1,866,363,293 packets and 4,478,862,225,755 bytes. The later public snapshot increased to 1,866,364,147 packets and 4,478,865,062,835 bytes as live counters advanced.

`ruleset_observed` proves bounded current topology and counter visibility only. It does not prove general firewall policy correctness, intended enforcement, or that every packet path traverses a particular rule. The verified-enforcement count remains 1 because only the dedicated Spamhaus contract is enforcement-verified.

## Privacy and safety boundary

The verifier publishes aggregate counts and fixed category labels only. It excludes table, chain, set, map, object, and jump-target names; addresses, prefixes, ports, interfaces, devices, elements, expressions, match values, comments, handles, priorities, full ruleset content, raw command output, credentials, and private keys.

No nftables or firewall mutation, service reload/restart, Fail2ban jail/action mutation, Unbound or RPZ change, DNS-answer change, proxy, routing, IDS-rule, reputation-list, authentication, or traffic-cutover change was performed.

## Remaining optional work

- review Network Defense freshness thresholds using observed timing;
- design protected historical Suricata retention with explicit privacy, size, time, authentication, rollback, and acceptance boundaries;
- review whether the public `edge1.ww.cx` access boundary should remain unchanged.

Each remains a separate design and authorization phase.

## Repository audit note

Commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d` accidentally created a one-byte verifier placeholder on `main`; commit `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a` removed it immediately before the feature branch was created. No runtime or production system was affected.
