# Security Observability and Spamhaus Live-State Handoff

Date: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Spamhaus verifier implementation merge: `e4002df7f7b6c523a76214804a3f5eb5b033561c`
Runtime wording-validation fix: `bfcbea8f971af864e5061824171da931225e1c26`
Deployment closeout merge: `bd29397c6373101837cf0bd749038b0d3ad31133`

## Completed live work

- Network Defense and Security Correlation deployed and accepted.
- `edge1.ww.cx` HTTPS status pages and JSON feeds accepted.
- Accessible Suricata alert drill-down deployed.
- Last-known-good cache, normalized schema, and source collector enrichment deployed.
- All 22 alerts in the accepted enrichment run retained ports, application protocol, SID/GID/revision, and flow ID.
- Read-only Spamhaus live-state verifier implemented, validated, merged, and installed on Edge1.
- Initial verifier deployment attempt rolled back safely after a case-sensitive wording assertion.
- PR #119 repaired the assertion and both required workflows passed.
- The corrected installer completed successfully without rollback.
- The exact live result was read from `acceptance-summary.json` and confirmed `active_verified`.

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Authoritative evidence

```text
Security observability:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Suricata collector enrichment:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z

Failed Spamhaus verifier attempt, rolled back:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180002Z

Successful Spamhaus verifier deployment:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z

Exact acceptance summary:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

## Final Spamhaus verifier state

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

`active_verified` is limited to the dedicated Spamhaus table, sets, hooked drop rules, updater result, timer state, freshness, and read-only contract. Other enforcement layers are not implied to be verified. Network Defense remains `limited`, DNS policy remains `not_staged`, and DNS enforcement remains disabled.

## Optional future work

- bounded general nftables aggregate visibility through a separate least-privilege verifier;
- bounded Fail2ban jail health and aggregate counts;
- review of Network Defense freshness thresholds;
- protected historical Suricata retention with explicit privacy, size, time, authentication, rollback, and acceptance boundaries;
- review of the public `edge1.ww.cx` access boundary.

Each remains a separate design and authorization phase.

## Safety boundary

No Spamhaus list refresh, filter reload, nftables mutation, firewall mutation, Unbound or RPZ change, DNS-answer change, Fail2ban, proxy, routing, IDS-rule, reputation-list, authentication, or traffic-cutover change was performed. The verifier exposes no addresses, set elements, full ruleset, raw command output, credentials, or private keys.
