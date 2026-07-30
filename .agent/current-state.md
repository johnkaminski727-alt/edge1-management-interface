# Current State

Last verified: 2026-07-30 00:42 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Fail2ban implementation merge: `725a09c1c488c2a0cb99931183e535e9fe726894`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- The accepted collector run published 22 enriched alerts with ports, application protocol, SID/GID/revision, and flow ID.
- DNS policy remains `not_staged`; DNS enforcement remains disabled.
- Traffic controls remain unchanged.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
```

## Verified Spamhaus live-state enforcement

The dedicated read-only Spamhaus verifier is live and directly verified:

```json
{
  "spamhaus_state": "active_verified",
  "spamhaus_enforcement_verified": true,
  "verified_enforcement_count": 1,
  "overall_state": "limited",
  "available_sources": 6,
  "source_count": 7,
  "dns_policy_state": "not_staged",
  "dns_enforcement_enabled": false,
  "traffic_controls_changed": false
}
```

Evidence:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

`active_verified` is limited to the dedicated Spamhaus table, expected sets and hooked rules, updater result, timer state, freshness, and safety contract.

## Verified Fail2ban live-state health

The read-only Fail2ban verifier implementation merged through PR #122 and was activated successfully on Edge1.

Exact accepted result:

```json
{
  "fail2ban_state": "active_observed",
  "fail2ban_health_observed": true,
  "fail2ban_enforcement_verified": false,
  "observed_jails": 7,
  "currently_banned": 0,
  "total_banned": 0,
  "verified_enforcement_count": 1,
  "overall_state": "limited",
  "available_sources": 7,
  "source_count": 8,
  "dns_policy_state": "not_staged",
  "dns_enforcement_enabled": false,
  "traffic_controls_changed": false
}
```

The service was active, its local control socket was reachable, and all seven sanitized reported jails were observed. Zero current and total bans is the truthful counter result at acceptance time; it is not an error.

Fail2ban remains `enforcement_verified: false` by design. The one verified enforcement source is the separate Spamhaus verifier. Jail presence and counters do not independently prove action installation or packet-path enforcement.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z/acceptance-summary.json
```

The verifier uses only `systemctl show fail2ban.service`, `fail2ban-client status`, and per-jail status queries. Public Network Defense receives aggregate metrics only. Banned addresses, log paths, raw client output, commands, credentials, and private keys remain excluded.

## Completion status

The bounded Security observability, Suricata enrichment, Spamhaus enforcement verification, and Fail2ban health-observability phases are implemented, merged, deployed, and accepted.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban jail/action, proxy, routing, Suricata rule, reputation-list, authentication-boundary, or traffic-control mutation was made by these observability phases. Payloads, packet bodies, raw EVE events, banned addresses, set elements, full firewall rulesets, credentials, and private keys remain excluded. Historical alert retention remains separate future work.
