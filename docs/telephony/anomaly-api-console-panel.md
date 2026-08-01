# Telephony Anomaly API and Console Panel

## Purpose

This repository increment exposes the accepted aggregate anomaly evaluator through one fixed read-only analytics API route and one fixed same-origin console route, then renders the bounded result in an informational console panel.

It does not deploy either service and does not authorize notification, enforcement, remediation, routing, service control, carrier action, call origination, or DTMF transmission.

## Analytics API route

The loopback analytics API adds:

```text
GET /api/telephony/platform/anomalies
```

The handler calls `evaluate_anomaly_indicators()` over the same synthetic aggregate health, call, and interconnect summaries returned by the existing repository contract.

The response mode must be:

```text
informational_no_enforcement
```

All non-GET write methods remain rejected with HTTP `405`.

## Separate exact proxy route

The console server retains the accepted three-entry `ANALYTICS_ROUTE_MAP` unchanged.

The anomaly path is a separate exact constant:

```text
/api/telephony/analytics/anomalies
```

It maps only to:

```text
/api/telephony/platform/anomalies
```

There is no prefix proxy, wildcard proxy, query-selected target, path-selected upstream, user-supplied URL, or direct browser access to port `8099`.

If the fixed upstream response is absent or invalid, the console server returns HTTP `503` with:

```json
{"error":"anomalies_unavailable"}
```

## Strict payload acceptance

The browser renders the panel only when all of these conditions are true:

- schema version is `1.0`;
- mode is `informational_no_enforcement`;
- exactly six indicators are present;
- every indicator ID is in the fixed local label map;
- every indicator state is recognized;
- every investigation target is in the fixed local anchor allowlist;
- every indicator has `automatic_action=false`;
- every top-level safety flag is explicitly false.

A payload that fails any condition is shown as unavailable. The browser does not partially trust or render an invalid response.

## Static investigation anchors

The only accepted links are same-page anchors:

```text
#analytics-health
#analytics-failures
#analytics-carriers
```

Input data cannot select a host, external URL, carrier portal, route, command, service, or operational action.

## Informational panel

The panel displays:

- overall informational state;
- fixed human-readable indicator labels;
- bounded observed values and units;
- `ok`, `watch`, `critical`, or `insufficient_data` state;
- sample size and fixed minimum sample;
- a clear statement that no automatic action is performed.

The panel does not display:

- carrier identifiers;
- destination-country labels;
- SIP-code labels;
- failure-class labels;
- component details;
- source aggregate maps;
- adjustable thresholds;
- customer, account, telephone, network, credential, route, message, media, recording, or free-form metadata.

All template values are HTML-escaped before insertion.

## No notification or enforcement

Neither the API nor the panel sends email, SMS, webhook, page, alarm, ticket, or external request. Neither blocks, throttles, quarantines, changes routes, changes carriers, modifies configuration, restarts services, originates calls or messages, transmits DTMF, or performs automatic remediation.

The words `watch` and `critical` identify informational review priority only. They are not authority to change production behavior or make carrier, fraud, regulatory, emergency-calling, root-cause, or certification claims.

## No runtime deployment

This repository increment does not install, reload, restart, or replace:

- `wwcx-telephony-analytics.service`;
- the loopback telephony console service;
- any collector, adapter, timer, or scheduled job.

The currently accepted analytics service may continue to execute an older worktree and may return `404` for the anomaly route until a separate bounded deployment is authorized. The currently running console may not contain the new panel until that separate deployment occurs.

No listener, firewall, DNS, certificate, database, credential, PBX, carrier, route, call, message, number, or DTMF path changes in this increment.

## Repository validation

From the repository root:

```bash
python3 tests/validate_telephony_anomaly_indicators.py
python3 tests/validate_telephony_analytics_api.py
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_telephony_anomaly_api_panel.py
node --check src/web/telephony/telephony.js
```

The focused test verifies:

- the original three-route map remains unchanged;
- the anomaly proxy uses separate exact constants;
- the API and same-origin anomaly paths are present;
- invalid upstream responses fail with bounded `503` behavior;
- the browser never addresses port `8099` or the platform route directly;
- all no-action safety flags are checked before rendering;
- investigation anchors are static and local;
- the fourth card has an independent unavailable state;
- JavaScript syntax remains valid.

## Acceptance boundary

Repository validation proves only that the synthetic, read-only endpoint and panel contract are internally bounded.

Live deployment requires a separate operator plan with:

1. accepted repository revision;
2. current analytics and console source provenance;
3. rollback copies or worktree references;
4. listener and service-state preflight;
5. bounded service update and restart authority;
6. all existing and new endpoint checks;
7. browser or rendered-panel verification;
8. index ownership verification;
9. protected evidence and rollback decision.
