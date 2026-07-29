# Suricata Alert Normalization Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Security Operations

## Triggering evidence

Live Security Operations drill-down was confirmed functional, but the displayed alert remained generic:

- title: `Unclassified Suricata alert`;
- risk: `unknown`;
- category and action available;
- signature ID, generator ID, revision, and flow/event ID shown as unknown.

The live cache contract was separately verified:

```json
{
  "cache": {
    "mode": "live",
    "stale": false,
    "snapshot_generated_at": "2026-07-29T08:01:50.630210+00:00",
    "age_seconds": 15,
    "source_error": null
  },
  "available": true,
  "alert_count": 30
}
```

## Repository implementation

| Capability | State |
| --- | --- |
| Actual nested Suricata signature precedence | Implemented |
| Explicit risk preservation | Implemented |
| Suricata numeric severity-to-risk mapping | Implemented |
| Source and destination ports | Implemented |
| Transport and application protocols | Implemented |
| SID, GID, revision, and flow/event identifier | Implemented |
| Category and action | Implemented |
| Generic meaning/recommendation improvement | Implemented |
| Payload and original raw alert exclusion | Validated |
| 50-alert publication bound | Preserved |
| Browser cache | Remains disabled by design |
| Edge1 last-known-good cache | Preserved |
| Historical alert archive | Not implemented |
| Traffic enforcement changes | None |

## Published contract

- Security Operations document schema: `2.0`.
- Alert schema: `wwcx.suricata-alert.v1`.
- Sanitized metadata explicitly reports that packet payload and raw event data are not included.

## Deployment state

Repository implementation is complete on the feature branch. Live deployment and acceptance remain pending merge, Edge1 fast-forward, UI publication, exporter refresh, downstream correlation/network-defense refresh, and evidence capture.

## Safety boundary

This change is read-only observability normalization. It does not modify Suricata rules, Suricata service configuration, nftables, firewall, DNS, resolver, routing, Fail2ban, proxy, reputation filtering, authentication, or traffic controls.
