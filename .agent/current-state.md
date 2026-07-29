# Current State

Last verified: 2026-07-29 18:08 UTC
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Spamhaus verifier implementation merge: `e4002df7f7b6c523a76214804a3f5eb5b033561c`
Runtime wording-validation fix: `bfcbea8f971af864e5061824171da931225e1c26`

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

- Alert cards provide accessible expand/collapse details.
- Expanded details are limited to sanitized allowlisted fields.
- Browser requests remain `cache: "no-store"`.
- Edge1 last-known-good caching distinguishes live data from stale fallback data.
- Security Operations schema is `2.0`.
- Public alert schema is `wwcx.suricata-alert.v1`.
- The source-controlled collector retains allowlisted ports, application protocol, SID/GID/revision, and flow identifiers.
- The final accepted collector run published 22 enriched alerts and refreshed Correlation and Network Defense without changing traffic controls.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
```

## Spamhaus live-state verifier

The read-only verifier implementation merged through PR #118 and the case-sensitive runtime-validation repair merged through PR #119.

Live installation completed successfully on Edge1:

```text
Spamhaus live-state observability deployment passed.
Evidence: /var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
```

Verified deployment facts:

- the checked-in installer completed without rollback;
- verifier and Network Defense acceptance completed consistently;
- contract `wwcx.spamhaus-live-state.v1` is deployed;
- the verifier publishes bounded counts and booleans only;
- Network Defense consumes the sanitized verifier snapshot;
- `traffic_controls_changed` remained false;
- DNS enforcement remained disabled;
- no Spamhaus refresh, filter reload, nftables mutation, firewall mutation, DNS, routing, Fail2ban, proxy, IDS, authentication, or traffic-control change occurred.

The exact accepted state was not included in the final terminal excerpt. It remains to be copied from:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

Allowed truthful values are `active_verified`, `partial`, `not_present`, or `unavailable`. Do not infer a specific value from the generic deployment-passed line.

## Completion status

The implementation, CI, rollback repair, and live deployment are complete. The only remaining evidence task is to record the exact accepted Spamhaus state from `acceptance-summary.json`.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban, proxy, routing, Suricata rule, reputation-list, authentication-boundary, or traffic-control change was made by these observability phases. Payloads, packet bodies, raw EVE events, set elements, full firewall rulesets, credentials, and private keys remain excluded. Historical alert retention remains separate future work.
