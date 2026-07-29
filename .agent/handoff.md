# Security Observability, Domain, and Suricata Normalization Handoff

Date: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative commit before this live-acceptance reconciliation: `6e3c51eaf03c908a310827aa1421a23f5ab52bfb`

## Completed work

- Network Defense bounded deployment completed.
- Security Correlation bounded deployment completed.
- Sanitized Security Controls inspection completed.
- Read-only Security observability acceptance passed.
- `edge1.ww.cx` HTTPS domain acceptance passed.
- Accessible Suricata alert drill-down deployed.
- Edge1 last-known-good Security Operations cache deployed and verified live.
- Nested Suricata alert normalization merged in PR #112.
- Bounded live activator merged in PR #113.
- Normalized Security Operations, Security Correlation, and Network Defense pipeline refreshed and accepted live.
- Live browser review confirmed that alert cards now show a classified title and known risk rather than the former generic `Unclassified Suricata alert` and `unknown` risk.

## Verified evidence

```text
Base Security observability acceptance:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain acceptance:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization activation:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Nested observability acceptance:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z/observability-acceptance
```

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Final normalized live snapshot

```json
{
  "ok": true,
  "alert_count": 30,
  "classified_alert_count": 30,
  "known_risk_count": 30,
  "source_port_count": 0,
  "destination_port_count": 0,
  "application_protocol_count": 0,
  "signature_id_count": 0,
  "cache_mode": "live",
  "cache_stale": false,
  "schema_version": "2.0",
  "alert_schema": "wwcx.suricata-alert.v1",
  "correlation_events": 30,
  "correlations": 0,
  "network_defense_state": "limited",
  "traffic_controls_changed": false
}
```

The live browser view confirmed the new classification and risk presentation. Live addresses and raw event content were intentionally not copied into repository records.

## Remaining collector-field gap

The normalized exporter and dashboard support source port, destination port, application protocol, SID, GID, revision, and flow/event identifiers. The current upstream collector snapshot did not supply ports, application protocol, or signature IDs for the observed 30 alerts, so those fields correctly remain unknown.

A future bounded collector enhancement may preserve these allowlisted EVE fields when present. It must retain:

- the sanitized `wwcx.suricata-alert.v1` contract;
- the 50-alert bound;
- packet-payload, raw-event, credential, and private-material exclusion;
- explicit stale/live cache labeling;
- downstream correlation and Network Defense acceptance;
- no traffic-control changes.

## Completion status

The bounded Security observability sequence, public HTTPS domain verification, Suricata drill-down, last-known-good caching, alert normalization, downstream refresh, and live acceptance are complete.

## Safety boundary

Not performed:

- Unbound or resolver configuration changes;
- RPZ staging or activation;
- DNS answer changes;
- nftables or firewall mutations;
- Fail2ban jail changes;
- proxy, routing, IDS rule, reputation-filter, or traffic-cutover changes;
- authentication-boundary changes;
- historical raw-alert publication;
- claims of active enforcement without direct evidence.
