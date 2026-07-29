# Suricata Collector Enrichment Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / Project Big Bird Operations Center
Status: live and accepted

## Triggering evidence

The earlier normalization phase classified every observed alert but proved that the historical collector discarded ports, application protocol, SID/GID/revision, and flow identifiers before publication.

The runtime collector was traced to the archived Project Big Bird V4.0.7 observability package. Its `suricata()` function retained only timestamp, signature, severity, category, and action.

## Ownership decision

| Asset | State |
| --- | --- |
| `server/bigbird_ops_collect.py` | Authoritative Edge1 collector source |
| `/usr/local/libexec/bigbird-ops-collect.py` | Live runtime installation target |
| Archived WW.CX V4.0.7 release collector | Historical release artifact; not editable canonical source |
| `bigbird-ops-push.service` | Existing one-shot publisher; unchanged |
| `bigbird-ops-push.timer` | Existing 120-second schedule; unchanged |

## Implemented source contract

- Collector release: `edge1-suricata-enrichment-r1`.
- Alert schema: `wwcx.suricata-source-alert.v1`.
- Source alert limit: 100.
- EVE input window: newest 5,000 lines.
- Retained: endpoints, ports, transport/application protocol, SID/GID/revision, flow/event identifier, signature, category, severity, action, timestamp.
- Excluded: payload, packet, original nested alert, raw EVE event, arbitrary metadata, credentials, private keys.

## Downstream compatibility

`security_operations_exporter.py` accepts both EVE-style `gid`/`rev` and source-contract `generator_id`/`revision` fields.

The public normalized output remains schema `2.0` with alert schema `wwcx.suricata-alert.v1`, a 50-alert bound, and payload/raw-event exclusion.

## Repository delivery

- PR: #115, `Enrich the Big Bird Suricata source collector`.
- Feature head: `b2e96dd1234b3e87509f0b7e90e6b34ddaf63f73`.
- Merge commit: `21b87664355e5f83173a630f24276389a6dcbbf6`.
- Edge1 Operator Validation: passed.
- Validate repository workflow: passed.

## Live acceptance

Activation command:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/activate-suricata-collector-enrichment.sh
```

Authoritative evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
```

Nested normalization evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation
```

Nested observability acceptance:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation/observability-acceptance
```

Final live result:

| Check | Result |
| --- | --- |
| Live EVE alerts | 22 |
| Source ports | 22 |
| Destination ports | 22 |
| Application protocols | 22 |
| Signature IDs | 22 |
| Generator IDs | 22 |
| Revisions | 22 |
| Flow IDs | 22 |
| Classified public alerts | 22 |
| Known-risk public alerts | 22 |
| Public cache | `live`, stale `false` |
| Correlation events | 22 |
| Correlations | 0 |
| Network Defense state | `limited` |
| DNS policy | `not_staged` |
| Enforcement | disabled |
| Traffic controls changed | `false` |

## Completion

The collector enrichment phase is complete. The old data-quality gap is closed for the observed live alerts, and the source-controlled collector is now the authoritative implementation.

## Safety boundary

This remains read-only telemetry enrichment. It did not reload Suricata, modify Suricata rules, change DNS or resolver behavior, alter nftables/firewall/Fail2ban/proxy/routing, change authentication, activate reputation enforcement, or change traffic controls.