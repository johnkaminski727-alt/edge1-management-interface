# Telephony Anomaly API and Panel Repository Acceptance — 2026-08-01

## Scope

This record accepts the repository implementation of one read-only aggregate anomaly API route, one separate exact same-origin proxy route, and one informational console panel.

It does not accept a runtime deployment, service restart, live source, notification path, enforcement action, route change, carrier action, call, message, DTMF transmission, or public exposure.

## Repository assets

```text
server/telephony_anomaly_indicators.py
server/telephony_analytics_api.py
server/telephony_status_server.py
src/web/telephony/index.html
src/web/telephony/telephony.js
src/web/telephony/telephony.css
tests/validate_telephony_anomaly_indicators.py
tests/validate_telephony_analytics_api.py
tests/validate_telephony_analytics_console_panels.py
tests/validate_telephony_anomaly_api_panel.py
docs/telephony/anomaly-indicators.md
docs/telephony/analytics-api.md
docs/telephony/anomaly-api-console-panel.md
```

## Accepted API boundary

The analytics repository contract adds exactly:

```text
GET /api/telephony/platform/anomalies
```

The endpoint evaluates the accepted synthetic aggregate health, call, and interconnect summaries. It returns six deterministic indicators in mode `informational_no_enforcement`.

All write methods remain rejected with HTTP `405`.

## Accepted proxy boundary

The original accepted three-entry analytics route map remains unchanged.

The anomaly route is handled separately with fixed constants:

```text
/api/telephony/analytics/anomalies
/api/telephony/platform/anomalies
```

There is no wildcard, prefix, query, path, or user-selected proxy. The browser does not directly access port `8099`.

An absent or invalid upstream response returns HTTP `503` and `anomalies_unavailable`.

## Accepted panel boundary

The fourth analytics card displays only:

- fixed indicator labels;
- derived observed values and units;
- informational state;
- sample and minimum-sample counts;
- fixed same-page investigation links;
- a no-action safety statement.

The browser validates schema version, fixed mode, exactly six known indicator IDs, known states, static investigation anchors, indicator `automatic_action=false`, and all top-level safety flags before rendering.

Invalid responses fail closed into a bounded unavailable state.

## Privacy result

The anomaly response and panel omit:

- carrier identifiers;
- country labels;
- SIP-code labels;
- failure-class labels;
- component detail;
- source aggregate maps;
- caller, called-party, customer, account, route, network, credential, message, media, recording, or free-form metadata.

All template values are escaped before insertion.

## No-action result

The implementation contains no:

- email, SMS, webhook, page, alarm, or ticket dispatch;
- traffic block, throttle, quarantine, or enforcement;
- automatic remediation;
- route, dial-plan, trunk, carrier, number, firewall, DNS, or certificate change;
- service start, stop, restart, or reload;
- call or message origination;
- DTMF transmission;
- live collector, database, credential, AMI/ARI, SIP-edge, log, packet, or carrier API access.

`watch` and `critical` are informational review priorities only.

## Repository validation gate

Required focused commands:

```bash
python3 tests/validate_telephony_anomaly_indicators.py
python3 tests/validate_telephony_analytics_api.py
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_telephony_anomaly_api_panel.py
node --check src/web/telephony/telephony.js
```

Final repository acceptance also requires both standard GitHub workflows to pass on the exact pull-request head:

- `Validate repository`;
- `Edge1 Operator Validation`.

## Explicitly unaccepted

The currently running analytics service was previously accepted against measured source hashes from a separate worktree. This repository change does not replace that source. The running service may return `404` for `/api/telephony/platform/anomalies` until a separate deployment occurs.

The running console service may not expose `/api/telephony/analytics/anomalies` or render the fourth card until a separate deployment occurs.

No service mutation, live endpoint verification, browser acceptance, listener change, runtime-source acceptance, protected deployment evidence, or rollback decision is included here.

## Decision

The repository implementation is acceptable only as a bounded, synthetic, read-only extension. Live use remains pending a separately authorized deployment and acceptance procedure.
