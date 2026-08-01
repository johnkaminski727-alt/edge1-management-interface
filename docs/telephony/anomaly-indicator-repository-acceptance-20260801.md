# Telephony Anomaly Indicator Repository Acceptance — 2026-08-01

## Scope

This record accepts the repository implementation of conservative informational indicators over privacy-minimized aggregate telephony summaries.

It does not accept a live endpoint, console panel, scheduled evaluation, notification path, enforcement action, source connection, or runtime deployment.

## Accepted repository assets

```text
server/telephony_anomaly_indicators.py
schemas/telephony/anomaly-indicators.schema.json
tests/validate_telephony_anomaly_indicators.py
docs/telephony/anomaly-indicators.md
docs/telephony/anomaly-indicator-repository-acceptance-20260801.md
```

Related documentation updated in this increment:

```text
docs/telephony/README.md
docs/telephony/operations-platform.md
```

## Input boundary

The evaluator accepts only the exact aggregate contracts returned by:

- `health_score()`;
- `summarize_calls()`;
- `analyze_interconnects()`.

It rejects:

- unknown fields;
- unsafe aggregate labels;
- long customer-like numeric identifiers;
- URI, email, and IP-address values;
- inconsistent call, answer, duration, category, failure, interconnect, attention, health-state, and latency totals.

It performs no file, network, database, credential, log, packet, AMI/ARI, SIP-edge, carrier, PBX, or service access.

## Accepted indicators

The evaluator emits exactly six indicators:

1. platform health score;
2. answer rate;
3. failure ratio;
4. dominant failure concentration;
5. interconnect attention ratio;
6. interconnect latency.

States are limited to:

- `ok`;
- `watch`;
- `critical`;
- `insufficient_data`.

Call-rate indicators require at least 20 calls, dominant failure concentration requires 10 failures, and interconnect indicators require at least two interconnects. Missing samples do not become performance findings.

## Privacy result

The output omits:

- carrier identifiers;
- destination-country labels;
- SIP response-code labels;
- failure-class labels;
- component detail;
- source aggregate maps;
- caller, called-party, account, route, network, credential, message, media, recording, or free-form metadata.

The output contains only bounded derived numbers, fixed thresholds, static reason codes, static same-page investigation anchors, and fixed safety flags.

## No-action result

Every indicator contains:

```text
automatic_action=false
```

The output safety object fixes all of these values to false:

```text
automatic_action
notification_dispatch
traffic_enforcement
route_change
service_control
```

There is no email, SMS, webhook, alarm, page, ticket, block, throttle, quarantine, route change, carrier action, service action, call, message, DTMF, number action, or automatic remediation path.

## Static investigation targets

The only investigation targets are fixed same-page console anchors:

```text
#analytics-health
#analytics-failures
#analytics-carriers
```

Input data cannot select a URL, host, command, carrier portal, external site, or operational action.

## Validation gate

Repository validation command:

```bash
python3 tests/validate_telephony_anomaly_indicators.py
```

The focused validation covers:

- healthy, watch, critical, and insufficient-data states;
- exact threshold boundaries;
- minimum sample gates;
- numeric SIP aggregate buckets;
- aggregate consistency;
- static investigation targets;
- omission of carrier, country, SIP-code, and failure labels;
- rejection of unknown fields and customer-like identifiers;
- absence of notification, enforcement, network, database, and service-control code paths.

Final repository acceptance requires the standard `Validate repository` and `Edge1 Operator Validation` workflows to pass for the exact branch head before merge.

## Explicitly unaccepted

The following remain unaccepted and require separate design, repository validation, and live authorization where applicable:

- analytics API integration;
- console rendering of indicators;
- scheduled or continuous evaluation;
- notification or ticket integration;
- automated enforcement or remediation;
- live source collection;
- runtime deployment or service restart;
- production threshold tuning presented as a carrier SLA;
- fraud, regulatory, emergency-calling, root-cause, or certification conclusions.

## Decision

The repository foundation is acceptable only as a deterministic, aggregate-only, no-action review aid. A `watch` or `critical` state is not authority to change production behavior.
