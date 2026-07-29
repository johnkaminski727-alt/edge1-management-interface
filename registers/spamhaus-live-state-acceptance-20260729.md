# Spamhaus Live-State Acceptance Record

Date: 2026-07-29
System: Edge1 / WW.CX Network Defense
Classification: internal, sanitized

## Deployment result

The checked-in installer completed successfully on Edge1 after the case-insensitive wording-validation correction merged through PR #119.

Reported terminal result:

```text
Spamhaus live-state observability deployment passed.
Live URL: http://127.0.0.1/edge1-status/network-defense/
Evidence: /var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
The verifier made no nftables, firewall, DNS, routing, Fail2ban, proxy, or traffic-control changes.
```

Authoritative evidence directory:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
```

Authoritative acceptance summary:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

## Exact accepted result

```json
{
  "ok": true,
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

## Verified facts

- deployment completed without rollback;
- the read-only verifier service and timer passed installer acceptance;
- Network Defense consumed the verifier snapshot consistently;
- Spamhaus live enforcement is directly verified as `active_verified`;
- the Spamhaus component contributes one verified enforcement source;
- the broader Network Defense state remains `limited` with 6 of 7 sources available;
- DNS policy remains `not_staged` and DNS enforcement remains disabled;
- `traffic_controls_changed` remained false;
- no Spamhaus list refresh, filter reload, nftables mutation, firewall mutation, DNS, routing, Fail2ban, proxy, IDS, authentication, or traffic-control change was performed.

## Interpretation boundary

`active_verified` applies specifically to the dedicated Spamhaus nftables table, expected sets and hooked drop rules, updater result, timer state, freshness, and read-only safety contract. It does not claim that DNS, general firewall, Fail2ban, proxy, or other enforcement layers are verified.
