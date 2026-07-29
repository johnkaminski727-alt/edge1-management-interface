# Suricata Alert Drill-down and Cache Plan

Date: 2026-07-29
System: Edge1 / WW.CX Security Operations
Status: implementation complete on feature branch; live deployment pending merge and Edge1 pull

## Confirmed prior behavior

- The Security Operations page rendered Suricata alerts as static article cards.
- No link, button, modal, expand/collapse control, or alert-detail route was attached to those cards.
- Browser HTTP caching was deliberately disabled for the live telemetry request with `cache: "no-store"` so stale security information was not presented as current.
- The exporter published only the newest 50 alerts into a single replace-in-place `security-operations.json` snapshot.
- The browser retained the last successful snapshot only in page memory during the current session; a reload did not provide persistent history.
- No Edge1-side last-known-good fallback or durable alert history was active.

## Implemented scope

### Phase 1 — alert drill-down

The Security Operations page now provides an accessible expand/collapse control for each alert card. The expanded view displays only approved fields already present in the sanitized snapshot:

- timestamp;
- risk;
- signature/title;
- source and destination;
- protocol and category when available;
- action when available;
- meaning and recommendation;
- rule, generator, revision, flow, or event identifiers when already present.

The page does not render packet payloads, credentials, raw logs, private keys, or unbounded raw event JSON.

### Phase 2 — last-known-good cache

The Security Operations exporter now retains the existing successful published snapshot as a bounded fallback when the upstream collector source is missing or unreadable.

Published cache metadata includes:

- cache mode: `live`, `last_known_good`, or `unavailable`;
- cached snapshot generation time;
- cache age;
- stale status;
- source error when fallback is used.

The dashboard clearly marks a cached fallback stale. The browser request remains `no-store`; the fallback belongs on Edge1, not in browser storage.

The exporter service runs from the repository path and its timer normally refreshes every 120 seconds. After deployment, manually starting `wwcx-security-operations.service` seeds the live cache immediately rather than waiting for the next timer run.

### Phase 3 — historical alert retention

Historical alert retention remains a separate feature from last-known-good caching. Before activation it requires:

- an explicit retention period and size cap;
- deduplication and stable event identifiers;
- sanitized schema validation;
- protected storage ownership and permissions;
- an authenticated or otherwise bounded query surface;
- backup, rollback, and live acceptance checks.

Do not expose an unbounded historical Suricata archive through the current public read-only endpoint.

## Validation

Repository validation includes:

- live snapshot and 50-alert bound checks;
- last-known-good fallback checks;
- unavailable-state checks when no valid cache exists;
- repeated-fallback warning deduplication;
- accessible drill-down markers;
- continued `cache: "no-store"` browser behavior;
- checks against browser storage and raw event rendering.

## Acceptance criteria

- Each alert opens and closes with mouse and keyboard.
- Expanded details are accessible and contain only approved fields.
- Existing filtering, sorting, download, and 60-second live refresh behavior remains functional.
- Live requests continue to bypass browser HTTP cache.
- Last-known-good fallback is clearly labeled stale and never presented as fresh live data.
- No IDS, firewall, DNS, routing, Fail2ban, proxy, resolver, or enforcement controls are changed.
