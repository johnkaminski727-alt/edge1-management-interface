# Suricata Collector Enrichment Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / Project Big Bird Operations Center

## Triggering evidence

Live Suricata normalization acceptance proved that all 30 observed alerts were classified and assigned a known risk, but the shared source snapshot supplied none of the following fields:

- source port;
- destination port;
- application protocol;
- signature ID.

The runtime collector was traced to the archived Project Big Bird V4.0.7 observability package. Its `suricata()` function retained only timestamp, signature, severity, category, and action.

## Ownership decision

| Asset | State |
| --- | --- |
| `server/bigbird_ops_collect.py` | New authoritative Edge1 collector source |
| `/usr/local/libexec/bigbird-ops-collect.py` | Runtime installation target |
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

`security_operations_exporter.py` now accepts both:

- existing EVE-style names `gid` and `rev`;
- source-contract names `generator_id` and `revision`.

The public normalized output remains schema `2.0` with alert schema `wwcx.suricata-alert.v1` and continues to publish `gid` and `rev` for UI compatibility.

## Validation state

| Validation | State |
| --- | --- |
| Representative EVE extraction | Implemented |
| Port and identifier bounds | Implemented |
| 100-alert source bound | Implemented |
| Non-alert event exclusion | Implemented |
| Payload/raw-event exclusion | Implemented |
| Source-contract to public-contract regression | Implemented |
| Rollback-safe activation | Implemented |
| Exact-head CI | Pending PR |
| Live Edge1 activation | Pending merge |
| Live ports/SID/flow acceptance | Pending activation |

## Activation

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/activate-suricata-collector-enrichment.sh
```

Expected evidence root:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/<timestamp>
```

## Safety boundary

This is a read-only telemetry enrichment. It does not reload Suricata, modify Suricata rules, change DNS or resolver behavior, alter nftables/firewall/Fail2ban/proxy/routing, change authentication, activate reputation enforcement, or change traffic controls.
