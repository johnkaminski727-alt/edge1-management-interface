# Telephony Aggregate Anomaly Indicators

## Purpose

`server/telephony_anomaly_indicators.py` evaluates conservative, deterministic indicators over the existing privacy-minimized aggregate health, call, and interconnect summaries.

The output is informational. It helps an operator decide where to inspect next; it does not diagnose root cause or authorize an operational action.

## Aggregate-only input boundary

The evaluator accepts only the exact dictionaries returned by:

- `health_score()`;
- `summarize_calls()`;
- `analyze_interconnects()`.

Every top-level field is required and unknown fields are rejected. Aggregate count maps are checked for safe bounded keys and internally consistent totals. Numeric SIP response buckets such as `200` and `503` are permitted, but long numeric sequences, addresses, URIs, email addresses, and unbounded labels are rejected.

The evaluator does not accept or retain:

- calling or called numbers;
- caller ID, ANI, DNIS, account codes, or customer identifiers;
- SIP/TEL URIs, Call-IDs, headers, SDP, or media data;
- IP or email addresses;
- message bodies, recordings, credentials, routes, or free-form metadata.

No carrier ID, destination country, SIP code, failure-class label, component detail, or raw aggregate map is copied into the result. Only bounded derived numbers and static reason codes are emitted.

## Indicator states

Every indicator uses one of four states:

- `ok` — the measured aggregate is inside the fixed informational boundary;
- `watch` — the measured aggregate crosses a conservative review threshold;
- `critical` — the measured aggregate crosses the higher-priority review threshold;
- `insufficient_data` — the sample does not meet the fixed minimum or required latency observations are absent.

`critical` is an operator-attention label, not an instruction to block traffic, change a route, restart a service, contact a provider, or make a regulatory or emergency-calling conclusion.

## Minimum sample gates

The evaluator does not classify small samples as performance anomalies:

- answer rate and overall failure ratio require at least `20` calls;
- dominant failure concentration requires at least `10` failure observations;
- interconnect attention ratio and latency require at least `2` interconnects;
- platform health score uses the five normalized platform components and therefore has a minimum sample of `1` aggregate score.

Indicators below these samples use `insufficient_data`. An insufficient indicator does not raise the overall state when another indicator has usable data.

## Fixed informational thresholds

### Platform health score

- `ok`: score `>= 90`;
- `watch`: score from `60` through `< 90`;
- `critical`: score `< 60`.

### Answer rate

With at least 20 calls:

- `ok`: answer rate `>= 70%`;
- `watch`: answer rate from `50%` through `< 70%`;
- `critical`: answer rate `< 50%`.

### Failure ratio

Failure ratio is the number of aggregate failure-class observations divided by total calls.

With at least 20 calls:

- `ok`: failure ratio `< 25%`;
- `watch`: failure ratio from `25%` through `< 50%`;
- `critical`: failure ratio `>= 50%`.

### Dominant failure concentration

Dominant concentration is the largest single failure-class count divided by all failure observations. The class label is not emitted.

With at least 10 failure observations:

- `ok`: concentration `< 60%`;
- `watch`: concentration from `60%` through `< 80%`;
- `critical`: concentration `>= 80%`.

### Interconnect attention ratio

With at least two interconnects:

- `ok`: attention ratio `< 25%`;
- `watch`: attention ratio from `25%` through `< 50%`;
- `critical`: attention ratio `>= 50%`.

### Interconnect latency

With at least two interconnects and both average and maximum latency observations:

- `critical` when average latency is at least `500 ms` or maximum latency is at least `1500 ms`;
- `watch` when average latency is at least `250 ms` or maximum latency is at least `750 ms`;
- otherwise `ok`.

These values are repository defaults for operational review. They are not carrier SLAs and do not prove endpoint, network, codec, routing, or provider fault.

## Static investigation targets

Each indicator points only to an existing same-page console anchor:

- `#analytics-health`;
- `#analytics-failures`;
- `#analytics-carriers`.

No input value can select a URL, host, route, command, carrier portal, external site, or operational action.

## Output contract

Schema:

```text
schemas/telephony/anomaly-indicators.schema.json
```

The output contains:

- schema version `1.0`;
- mode `informational_no_enforcement`;
- aggregate overall state;
- exactly six indicators;
- fixed safety flags that are all false.

Each indicator contains only its fixed ID, state, derived observed value, unit, minimum sample, actual sample size, fixed thresholds, static reason code, static investigation target, and `automatic_action=false`.

## No notification or enforcement

This repository increment contains no:

- email, SMS, webhook, page, alarm, or ticket dispatch;
- service start, stop, restart, or reload;
- call or message origination;
- DTMF transmission;
- route, dial-plan, trunk, carrier, number, firewall, DNS, or certificate change;
- traffic blocking, throttling, quarantine, fraud enforcement, or automatic remediation;
- database, AMI/ARI, SIP-edge, carrier API, log, or packet source access;
- scheduled job, timer, runtime deployment, or live evaluation.

A future endpoint or console integration must remain read-only, use accepted aggregate inputs, preserve the fixed thresholds and sample gates, and receive separate repository and live acceptance.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_anomaly_indicators.py
```

The validation covers:

- healthy, watch, critical, and insufficient-data outcomes;
- exact answer-rate and failure-ratio boundaries;
- numeric SIP aggregate keys;
- sample gates;
- dominant failure concentration without label disclosure;
- interconnect attention and latency thresholds;
- fixed investigation anchors;
- absence of carrier, country, SIP-code, and failure-label leakage;
- rejection of unknown fields, customer-like identifiers, inconsistent totals, inconsistent health state, and invalid latency relationships;
- absence of network, database, notification, service-control, or enforcement code paths.

## Acceptance boundary

An indicator is a deterministic comparison against fixed aggregate thresholds. It is not machine learning, a forecast, a root-cause diagnosis, a carrier-performance certification, a fraud determination, a service-level finding, an emergency-calling assessment, or authority to take action.
