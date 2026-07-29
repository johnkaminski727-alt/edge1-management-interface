# Suricata Alert Drill-down and Cache Plan

Date: 2026-07-29
System: Edge1 / WW.CX Security Operations
Status: planned, not active

## Confirmed current behavior

- The Security Operations page renders Suricata alerts as static article cards.
- No link, button, modal, expand/collapse control, or alert-detail route is currently attached to those cards.
- Browser HTTP caching is deliberately disabled for the live telemetry request with `cache: "no-store"` so stale security information is not presented as current.
- The exporter publishes only the newest 50 alerts into a single replace-in-place `security-operations.json` snapshot.
- The browser retains the last successful snapshot only in page memory during the current session; a reload does not provide persistent history.
- No durable alert-history cache is currently active.

## Next implementation

### Phase 1 — alert drill-down

Add an accessible expand/collapse control to each alert card. The expanded view should display only approved fields already present in the current sanitized snapshot, including:

- timestamp;
- risk;
- signature/title;
- source and destination;
- protocol and category when available;
- meaning and recommendation;
- rule identifiers when already included in the sanitized snapshot.

Do not display packet payloads, credentials, raw logs, private keys, or unbounded raw event JSON.

### Phase 2 — last-known-good cache

Add a bounded last-known-good fallback to the Security Operations exporter so that a temporary collector failure can publish the most recent valid sanitized snapshot with explicit stale/cache metadata.

Required metadata:

- cache mode: `live` or `last_known_good`;
- cached snapshot generation time;
- cache age;
- stale status;
- source error when fallback is used.

The browser request must remain `no-store`; this cache belongs on Edge1, not in an unauthenticated browser.

### Phase 3 — historical alert retention

Historical alert retention is a separate feature from last-known-good caching. Before activation it requires:

- an explicit retention period and size cap;
- deduplication and stable event identifiers;
- sanitized schema validation;
- protected storage ownership and permissions;
- an authenticated or otherwise bounded query surface;
- backup, rollback, and live acceptance checks.

Do not expose an unbounded historical Suricata archive through the current public read-only endpoint.

## Acceptance criteria

- Each alert can be opened and closed with mouse and keyboard.
- Expanded details are accessible and contain only approved fields.
- Existing filtering, sorting, download, and 60-second live refresh behavior remains functional.
- Live requests continue to bypass browser HTTP cache.
- Last-known-good fallback is clearly labeled stale and never presented as fresh live data.
- No IDS, firewall, DNS, routing, Fail2ban, proxy, resolver, or enforcement controls are changed.
