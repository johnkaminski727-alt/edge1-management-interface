# Current State

Last verified: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative commit before this live-acceptance reconciliation: `6e3c51eaf03c908a310827aa1421a23f5ab52bfb`

## Verified live security observability

- Network Defense observability deployed successfully on Edge1.
- Network Defense evidence: `/var/lib/wwcx-deployment-evidence/network-defense/20260729T060015Z`.
- Security Correlation observability deployed successfully.
- Security Correlation evidence: `/var/lib/wwcx-deployment-evidence/security-correlation/20260729T061441Z`.
- Sanitized Security Controls inspection completed successfully.
- Security Controls evidence: `/var/lib/wwcx-deployment-evidence/security-controls-inspection/20260729T061447Z`.
- Successful base observability acceptance evidence: `/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z`.
- Security Correlation is live and consumed by Network Defense.
- DNS policy remains `not_staged`.
- Enforcement remains disabled.
- Traffic controls remain unchanged.

## Verified domain exposure

- `edge1.ww.cx` resolved on Edge1 to `89.147.109.253`.
- Apache exposed the `edge1.ww.cx` name-based virtual host on ports 80 and 443.
- HTTP redirected to `https://edge1.ww.cx/edge1-status/`.
- The installed Let's Encrypt certificate covered `edge1.ww.cx`, `pbx.ww.cx`, and `sip.ww.cx` and was valid through 2026-10-17 01:27:37 UTC at verification time.
- The following HTTPS pages passed content checks:
  - `https://edge1.ww.cx/edge1-status/`;
  - `https://edge1.ww.cx/edge1-status/security/`;
  - `https://edge1.ww.cx/edge1-status/security/correlation.html`;
  - `https://edge1.ww.cx/edge1-status/network-defense/`.
- Domain acceptance evidence: `/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z`.

## Verified Suricata drill-down and caching

- Alert cards are accessible mouse- and keyboard-operated expand/collapse controls.
- Expanded details are limited to sanitized allowlisted fields.
- Browser requests remain `cache: "no-store"`.
- Edge1 last-known-good caching is active and clearly distinguishes live from stale fallback data.
- The live cache was verified with `mode: live`, `stale: false`, and 30 alerts.

## Verified Suricata normalization

The normalized alert contract and bounded activator were merged and deployed:

- PR #112: nested alert normalization;
- merge commit: `be2880d49ab842b1876e6c2898f1acced6bb78f1`;
- PR #113: bounded live activator;
- merge commit: `6e3c51eaf03c908a310827aa1421a23f5ab52bfb`.

Live activation command:

```bash
sudo bash ./deploy/activate-suricata-alert-normalization.sh
```

Authoritative evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
```

Nested observability acceptance:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z/observability-acceptance
```

Verified live result:

- 30 alerts published;
- 30 alerts classified;
- 30 alerts assigned a known risk;
- cache mode `live`;
- cache stale `false`;
- Security Operations schema `2.0`;
- alert schema `wwcx.suricata-alert.v1`;
- Security Correlation refreshed with 30 events and 0 correlations;
- Network Defense refreshed with state `limited`;
- DNS policy remained `not_staged`;
- enforcement remained disabled;
- `traffic_controls_changed: false`.

## Remaining data-quality gap

The current upstream collector snapshot did not include:

- source ports;
- destination ports;
- application protocol;
- signature IDs.

All 30 live records were still classified and assigned a known risk. The normalized exporter correctly left unsupported metadata absent rather than inventing values. Future work may enhance the collector to preserve these allowlisted EVE fields while retaining payload/raw-event exclusion and the 50-alert bound.

## Completion status

The bounded Security observability deployment, domain exposure, Suricata drill-down, last-known-good caching, normalized alert schema, downstream refresh, and live acceptance are complete.

## Safety boundary

No DNS, resolver, RPZ, firewall, nftables, Fail2ban, proxy, routing, Suricata rule, reputation-filter, authentication-boundary, or traffic-control change was made. Historical alert retention and collector enrichment remain separate future work.
