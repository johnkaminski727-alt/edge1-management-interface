# Current State

Last verified: 2026-07-29 18:45 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Latest completed closeout merge: `8f1319150e180fcf4b06bc30a122e4541f65fd02`

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

## Fail2ban live-state observability implementation

Current feature branch:

```text
feature/fail2ban-live-state-observability-20260729
```

Implemented assets:

- `server/fail2ban_live_state_verifier.py`;
- `server/network_defense_fail2ban_exporter.py`;
- `deploy/systemd/wwcx-fail2ban-live-state.service`;
- `deploy/systemd/wwcx-fail2ban-live-state.timer`;
- updated capability-free `wwcx-network-defense.service` wiring;
- `deploy/install-fail2ban-live-state-observability.sh`;
- verifier, integration, runtime-wiring, privacy, stale-state, and deployment-safety tests;
- architecture document and implementation register.

Verifier contract:

```text
wwcx.fail2ban-live-state.v1
```

Private runtime snapshot:

```text
/var/lib/bigbird-security/fail2ban/live-state.json
```

The verifier uses only:

```text
systemctl show fail2ban.service ...
fail2ban-client status
fail2ban-client status <sanitized-jail-name>
```

Published evidence is bounded to service/socket status, sanitized jail names in the private snapshot, and aggregate/per-jail counters. Banned addresses, log paths, raw client output, commands, credentials, and private keys are excluded. Public Network Defense receives aggregate metrics only.

Truthful states are `active_observed`, `partial`, `inactive`, `not_installed`, and `unavailable`. Every state keeps `enforcement_verified: false` and `traffic_controls_changed: false`; this phase does not claim packet enforcement.

The root verifier has no Linux capabilities and is restricted to AF_UNIX. Network Defense remains capability-free. The installer does not start, stop, reload, restart, or reconfigure `fail2ban.service`.

## Completion status

The repository implementation is complete on the feature branch. Exact-head CI, merge, and bounded Edge1 activation remain pending.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban jail/action, proxy, routing, Suricata rule, reputation-list, authentication-boundary, or traffic-control mutation is included. Payloads, packet bodies, raw EVE events, banned addresses, set elements, full firewall rulesets, credentials, and private keys remain excluded. Historical alert retention remains separate future work.
