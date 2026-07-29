# Suricata Alert Normalization Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Security Operations
Status: live accepted

## Triggering evidence

Live Security Operations drill-down was confirmed functional, but the displayed alert remained generic:

- title: `Unclassified Suricata alert`;
- risk: `unknown`;
- category and action available;
- signature ID, generator ID, revision, and flow/event ID shown as unknown.

The live cache contract was separately verified with `mode: live`, `stale: false`, and a bounded 30-alert snapshot.

## Repository implementation

| Capability | State |
| --- | --- |
| Actual nested Suricata signature precedence | Implemented and live |
| Explicit risk preservation | Implemented and live |
| Suricata numeric severity-to-risk mapping | Implemented and live |
| Source and destination ports | Supported; absent in current collector output |
| Transport protocol | Implemented and live |
| Application protocol | Supported; absent in current collector output |
| SID, GID, revision, and flow/event identifier | Supported; IDs absent in current collector output |
| Category and action | Implemented and live |
| Generic meaning/recommendation improvement | Implemented and live |
| Payload and original raw alert exclusion | Validated |
| 50-alert publication bound | Preserved |
| Browser cache | Disabled by design |
| Edge1 last-known-good cache | Active |
| Historical alert archive | Not implemented |
| Traffic enforcement changes | None |

## Published contract

- Security Operations document schema: `2.0`.
- Alert schema: `wwcx.suricata-alert.v1`.
- Sanitized metadata explicitly reports that packet payload and raw event data are not included.

## Live acceptance

Activation command:

```bash
sudo bash ./deploy/activate-suricata-alert-normalization.sh
```

Authoritative evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
```

Observability acceptance evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z/observability-acceptance
```

Verified live result:

| Metric | Result |
| --- | --- |
| Alert count | 30 |
| Classified alerts | 30 |
| Known-risk alerts | 30 |
| Source-port fields present | 0 |
| Destination-port fields present | 0 |
| Application-protocol fields present | 0 |
| Signature-ID fields present | 0 |
| Cache mode | `live` |
| Cache stale | `false` |
| Correlation events | 30 |
| Correlations | 0 |
| Network Defense state | `limited` |
| DNS policy | `not_staged` |
| Enforcement enabled | `false` |
| Traffic controls changed | `false` |

The zero counts for ports, application protocol, and signature IDs identify a collector-source gap. The exporter and dashboard support these allowlisted fields and correctly leave them absent when the upstream snapshot does not provide them.

## Safety boundary

This change is read-only observability normalization. It did not modify Suricata rules, Suricata service configuration, nftables, firewall, DNS, resolver, routing, Fail2ban, proxy, reputation filtering, authentication, or traffic controls.
