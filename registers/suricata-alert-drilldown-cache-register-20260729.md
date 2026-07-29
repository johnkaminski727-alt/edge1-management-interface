# Suricata Alert Drill-down and Cache Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Security Operations

## Current status

| Capability | State | Evidence |
| --- | --- | --- |
| Live Suricata snapshot | Active | `/edge1-status/security-operations.json` |
| Alert filtering and sorting | Active | Security Operations dashboard |
| Alert click/drill-down | Not implemented | Alert cards have no interactive control or click handler |
| Browser HTTP cache | Disabled by design | Live request uses `cache: "no-store"` |
| In-page last successful snapshot | Active for current browser session only | `latestSnapshot` remains in memory on refresh failure |
| Edge1 last-known-good cache | Not implemented | Exporter replaces the current JSON snapshot |
| Historical alert retention | Not implemented | Exporter limits output to newest 50 alerts |

## Decision

The next bounded security-visibility phase is:

1. accessible click-to-expand alert details using only current sanitized fields;
2. an Edge1-side last-known-good cache with explicit stale metadata;
3. separately designed historical retention only after retention, privacy, ownership, access-boundary, rollback, and acceptance requirements are defined.

Browser caching will remain disabled because current security telemetry must not be presented as fresh when stale.

## Safety boundary

This work must not modify Suricata rules or service state, firewall, nftables, DNS, resolver, routing, Fail2ban, proxy, reputation filtering, or traffic controls. It must not publish packet payloads, credentials, raw logs, private keys, or an unbounded public alert archive.
