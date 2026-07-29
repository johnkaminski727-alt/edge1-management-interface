# Security Observability and Suricata Collector Enrichment Handoff

Date: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative implementation merge: `21b87664355e5f83173a630f24276389a6dcbbf6`

## Completed work

- Network Defense bounded deployment completed.
- Security Correlation bounded deployment completed.
- Read-only Security observability acceptance passed.
- `edge1.ww.cx` HTTPS domain acceptance passed.
- Accessible Suricata alert drill-down deployed.
- Edge1 last-known-good Security Operations cache deployed and verified.
- Nested Suricata alert normalization deployed.
- Source-controlled Big Bird collector enrichment merged through PR #115 and activated on Edge1.
- Security Operations, Correlation, and Network Defense were refreshed and accepted after collector activation.

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Authoritative evidence

```text
Base Security observability acceptance:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain acceptance:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization activation:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Suricata collector enrichment:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z

Nested normalization activation:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation

Nested observability acceptance:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation/observability-acceptance
```

## Final live collector result

```json
{
  "ok": true,
  "alert_count": 22,
  "source_port_count": 22,
  "destination_port_count": 22,
  "application_protocol_count": 22,
  "signature_id_count": 22,
  "generator_id_count": 22,
  "revision_count": 22,
  "flow_id_count": 22,
  "correlation_events": 22,
  "correlations": 0,
  "network_defense_state": "limited",
  "traffic_controls_changed": false
}
```

The normalized public feed also verified:

- 22 classified alerts;
- 22 alerts with a known risk;
- cache mode `live` and stale `false`;
- schema `2.0` and alert schema `wwcx.suricata-alert.v1`;
- read-only correlation;
- DNS policy `not_staged`;
- enforcement disabled.

Live addresses and raw event content were intentionally not copied into repository records.

## Collector ownership

- Authoritative source: `server/bigbird_ops_collect.py`.
- Runtime target: `/usr/local/libexec/bigbird-ops-collect.py`.
- Collector release: `edge1-suricata-enrichment-r1`.
- Source schema: `wwcx.suricata-source-alert.v1`.
- The archived WW.CX V4.0.7 collector remains a historical release artifact.
- Existing `bigbird-ops-push.service` and timer remain unchanged.

## Completion status

The bounded Security observability sequence, public HTTPS exposure, alert drill-down, caching, normalization, collector enrichment, downstream refresh, and live acceptance are complete.

## Optional future work

- protected historical alert retention with explicit retention and authenticated query boundaries;
- least-privilege periodic nftables and Fail2ban visibility;
- dedicated Spamhaus live-state verification;
- review of the public `edge1.ww.cx` access boundary.

Each remains a separate design and authorization phase.

## Safety boundary

Not performed:

- Unbound or resolver configuration changes;
- RPZ staging or activation;
- DNS answer changes;
- nftables or firewall mutations;
- Fail2ban jail changes;
- proxy, routing, IDS rule, reputation-filter, or traffic-cutover changes;
- authentication-boundary changes;
- payload, packet-body, or raw-EVE publication;
- claims of active enforcement without direct evidence.