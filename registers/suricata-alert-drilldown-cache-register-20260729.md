# Suricata Alert Drill-down and Cache Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Security Operations

## Current status

| Capability | State | Evidence |
| --- | --- | --- |
| Live Suricata snapshot | Active | `/edge1-status/security-operations.json` |
| Alert filtering and sorting | Active | Security Operations dashboard |
| Alert click/drill-down | Implemented on feature branch; live deployment pending | Accessible button, `aria-expanded`, bounded sanitized detail fields |
| Browser HTTP cache | Disabled by design | Live request continues to use `cache: "no-store"` |
| In-page last successful snapshot | Active for current browser session | `latestSnapshot` remains in memory on refresh failure |
| Edge1 last-known-good cache | Implemented on feature branch; live deployment pending | Exporter reuses the last valid published snapshot and marks it stale |
| Historical alert retention | Not implemented | Current published view remains bounded to newest 50 alerts |

## Implemented decision

The bounded security-visibility enhancement now includes:

1. accessible click-to-expand alert details using only current sanitized fields;
2. an Edge1-side last-known-good fallback with explicit stale/cache metadata;
3. automated validation for live mode, fallback mode, missing-cache behavior, warning deduplication, UI accessibility markers, and browser no-store behavior.

Browser caching remains disabled because current security telemetry must not be presented as fresh when stale.

The exporter timer normally refreshes every 120 seconds. After merge and Edge1 pull, a manual start of `wwcx-security-operations.service` seeds live cache metadata immediately.

## Historical retention boundary

The last-known-good fallback is not a historical database. Historical alert retention remains deferred until the following are defined and accepted:

- retention period and size cap;
- deduplication and stable event identifiers;
- sanitized schema;
- protected ownership and permissions;
- authenticated or otherwise bounded query surface;
- backup, rollback, and live acceptance checks.

## Safety boundary

This work does not modify Suricata rules or service state, firewall, nftables, DNS, resolver, routing, Fail2ban, proxy, reputation filtering, or traffic controls. It does not publish packet payloads, credentials, raw logs, private keys, or an unbounded public alert archive.
