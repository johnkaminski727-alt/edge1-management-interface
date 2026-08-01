# Telephony Analytics Console Panels

## Purpose

The Big Bird telephony console now has read-only panels for:

- aggregate platform health score and component states;
- aggregate call totals, answer rate, duration, and SIP failure classes;
- sanitized carrier utilization and aggregate interconnect state and latency.

The panels consume only the already accepted loopback analytics API. They do not read raw CDRs, SIP traces, credentials, caller or called numbers, message bodies, recordings, SDP, or customer records.

## Exact same-origin routes

The browser remains on the loopback telephony console and calls exactly three same-origin paths:

```text
/api/telephony/analytics/health
/api/telephony/analytics/calls
/api/telephony/analytics/interconnects
```

`server/telephony_status_server.py` maps those exact paths to fixed loopback targets on `127.0.0.1:8099`:

```text
/api/telephony/platform/health
/api/telephony/platform/calls/summary
/api/telephony/platform/interconnects/summary
```

There is no wildcard proxy, user-selected upstream, query-driven target, or browser access to port `8099`. The server accepts only the exact route-map keys.

## Privacy-minimized panels

The health panel displays the bounded weighted score, overall state, and normalized component states.

The call-outcome panel displays only aggregate counts, answer rate, average duration, and stable SIP failure classes.

The carrier/interconnect panel displays opaque sanitized carrier identifiers with aggregate event counts, plus total interconnects, attention count, state counts, and observed aggregate latency. It does not claim a carrier SLA, route readiness, or end-to-end interoperability.

All values inserted through HTML templates are escaped before rendering. The panels do not display call identifiers, telephone numbers, SIP URIs, network addresses, names, or free-form metadata.

## Failure behavior

The three requests use independent settled results. If one analytics route is unavailable:

- the existing operational console snapshot continues to render;
- unaffected analytics panels continue to render;
- the unavailable panel shows a bounded unavailable state;
- the same-origin proxy returns HTTP `503` with `analytics_unavailable` when its fixed upstream response is absent or invalid.

No fixture is used to fabricate aggregate analytics results.

## Read-only boundary

This increment adds no POST, PUT, PATCH, DELETE, configuration, route, carrier, PBX, call, DTMF, number-management, database, credential, service-control, or public-listener capability.

The console server remains loopback-only. The analytics API remains loopback-only. The panels are observational and do not establish production routing, emergency-calling readiness, provider acceptance, regulatory status, or carrier interoperability.

## No deployment in this increment

This repository increment does not install, reload, restart, or deploy the console or analytics service. Live activation requires a separate bounded operator action that verifies the accepted repository revision, current service source, listener scope, endpoint behavior, and rollback path.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_telephony_console.py
python3 tests/validate_telephony_analytics_api.py
node --check src/web/telephony/telephony.js
```

The focused validation imports the exact route map, rejects arbitrary proxy or write markers, verifies browser isolation from port `8099`, confirms panel and accessibility markers, and checks escaped rendering and bounded unavailable states.
