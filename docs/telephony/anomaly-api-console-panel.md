# Telephony Anomaly API and Console Panel

## Purpose

This increment exposes the accepted deterministic aggregate anomaly evaluator through the existing loopback analytics service and adds one informational panel to the private telephony console.

The feature remains observational. It does not dispatch notifications, block traffic, change routes, control services, originate calls or messages, transmit DTMF, query a database, read credentials, or trigger automatic remediation.

## Existing same-origin route

The browser continues to use the already accepted fixed same-origin route:

```text
/api/telephony/analytics/health
```

The loopback analytics API extends that health response with one bounded `anomalies` object. The existing score, overall status, and component fields remain unchanged.

No new console-server proxy mapping, wildcard path, query-selected target, or browser access to port `8099` is introduced.

## Dedicated loopback route

Operators and future protected validation tooling may read the same bounded contract directly from the analytics service at:

```text
/api/telephony/platform/anomalies
```

That route is available only through the loopback-bound analytics API. POST remains rejected with HTTP `405`, and no PUT, PATCH, or DELETE handler exists.

## Fail-closed browser validation

`telephony-anomalies.js` renders a payload only when all of the following are true:

- schema version is exactly `1.0`;
- mode is exactly `informational_no_enforcement`;
- overall and per-indicator states are from the accepted state set;
- exactly the six accepted indicator identifiers are present once each;
- every indicator has `automatic_action=false`;
- every top-level safety flag is `false`;
- investigation targets are limited to the three established same-page aggregate panels;
- numeric, sample-size, unit, and reason-code fields are bounded.

Any missing, malformed, action-capable, unknown, or unavailable response produces a bounded unavailable message rather than partial rendering.

All displayed values pass through HTML escaping. The panel does not display carrier identifiers, destination countries, SIP codes, failure labels, component detail maps, customer identifiers, telephone numbers, SIP URIs, IP addresses, credentials, or free-form metadata.

## UI boundary

The panel displays:

- overall informational state;
- six fixed indicator names;
- state, observed aggregate value, unit, sample size, and minimum sample;
- local links to the existing aggregate health, failure, or carrier/interconnect panel.

The links are static same-page anchors. They are not user-controlled URLs and do not invoke an action.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_anomaly_indicators.py
python3 tests/validate_telephony_analytics_api.py
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_telephony_anomaly_api_panel.py
node --check src/web/telephony/telephony-anomalies.js
```

The focused validation imports the API with deterministic aggregate summaries, verifies nested and dedicated anomaly contracts, checks all no-action flags, scans the browser assets for direct-port and write-method markers, and verifies the fixed same-origin route and static anchor allowlists.

## No deployment in this increment

This repository change does not install, enable, start, stop, restart, reload, or replace either the analytics service or the console service. It does not modify systemd units, listeners, firewall rules, DNS, certificates, credentials, source data, or runtime worktrees.

A later bounded deployment must verify:

1. clean canonical `main`;
2. runtime source hashes against the accepted commit;
3. loopback-only listeners on the existing ports;
4. GET behavior and POST rejection;
5. the nested anomaly contract from the fixed same-origin health route;
6. rendered unavailable behavior for malformed or missing anomaly data;
7. service and repository rollback paths;
8. preserved `.git/index` ownership.
