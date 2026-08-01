# Edge1 Telephony Operations Platform

## Purpose

The Edge1 Telephony Operations Platform consolidates PBX, SIP interconnect, carrier, numbering, routing, health, and call-analysis capabilities into the existing loopback-only Big Bird telephony console.

It extends the existing fixture-backed and live read-only status service. It does not replace Asterisk, Kamailio/OpenSIPS, carrier portals, the numbering registry, or existing operational evidence systems.

## Read-only production boundary

The delivered foundation is strictly observational and analytical.

Allowed behavior:

- normalize sanitized collector output;
- calculate bounded health scores;
- aggregate CDR-style call events;
- classify SIP response outcomes;
- summarize interconnect state and latency;
- evaluate conservative aggregate review indicators;
- generate operator-facing recommendations from already-authorized data;
- record privacy-minimized evidence that an aggregate report was generated.

Prohibited behavior:

- changing dial plans, routes, trunks, extensions, registrations, credentials, or carrier settings;
- restarting or reloading production telephony services;
- originating calls or messages;
- changing emergency-calling behavior;
- porting, provisioning, assigning, or releasing numbers;
- enabling STIR/SHAKEN signing;
- exposing audio, message bodies, secrets, or unredacted customer records.

## Architecture

```text
Asterisk / SIP edge / registries / approved CDR source
                         |
       separately reviewed minimization boundary
                         |
             normalized sanitized records
                         |
    server/telephony_sanitized_adapters.py
                         |
          server/telephony_platform.py
                 |                 |
          health analysis      call analysis
                 |                 |
 server/telephony_anomaly_indicators.py
                 |
       loopback analytics API on 127.0.0.1:8099
                         |
       three fixed same-origin console routes
                         |
      privacy-minimized console panels on 8096

separately reviewed report generator
                         |
          aggregate report + artifact hashes
                         |
         server/telephony_report_audit.py
                         |
      protected owner-only hash-chained JSONL
```

The browser must continue to use the localhost-only server boundary. It must never connect directly to PBX, carrier, SBC, media, database administration interfaces, or the separate analytics port.

The sanitized adapter library is not a live collector. It performs no file, network, database, credential, service-control, PBX, carrier, route, or configuration access.

The anomaly evaluator consumes aggregate summaries only and has no notification, enforcement, service-control, routing, or automatic-remediation path.

The report-audit module does not generate reports or read source data. It accepts only a pre-minimized event describing an already-generated aggregate report.

## Management and analysis capabilities

### Platform health

`health_score()` evaluates five normalized domains:

- PBX
- SIP/interconnect
- routing
- registry
- analytics

The score is informational. An apparently healthy score does not certify production routing, emergency calling, carrier acceptance, legal status, or regulatory readiness.

### Call analytics

`summarize_calls()` accepts privacy-minimized `CallEvent` records and produces:

- total and answered calls;
- answer rate;
- total and average duration;
- inbound, outbound, internal, and unknown direction counts;
- disposition counts;
- carrier utilization;
- destination-country distribution;
- SIP-code distribution;
- failure-class distribution.

The aggregate interface intentionally does not require calling-party numbers, called-party numbers, SIP credentials, recording paths, audio, message contents, or customer names.

### Sanitized event adapters

`server/telephony_sanitized_adapters.py` supplies fail-closed normalization for already-sanitized CDR records and SIP outcome events.

Canonical schemas:

- `schemas/telephony/sanitized-cdr-record.schema.json`;
- `schemas/telephony/sanitized-sip-event.schema.json`.

The adapters:

- require schema version `1.0`, opaque source IDs, and UTC observation timestamps;
- normalize bounded direction, disposition, response-code, carrier, country, and duration aliases;
- derive only conservative SIP progress, completion, failure, or unknown outcomes when disposition is absent;
- reject unknown fields instead of silently retaining or dropping them;
- reject calling and called numbers, caller ID, ANI, DNIS, SIP/TEL URIs, IP and email addresses, Call-IDs, headers, credentials, SDP, media, recordings, message bodies, names, long numeric identifiers, and nested free-form metadata;
- fail an entire batch on the first rejected record;
- emit only the bounded `CallEvent` fields and minimal provenance metadata.

Passing an adapter validates only the input shape and minimization boundary. It does not prove that the upstream source was lawfully accessed, fully minimized, operationally complete, or suitable for production use.

### SIP failure classification

`classify_sip_failure()` maps common SIP response codes to stable operational categories. Categories are diagnostic hints, not proof of root cause. Operators must correlate them with approved logs, route configuration, carrier evidence, and timestamps.

### Interconnect analysis

`analyze_interconnects()` summarizes normalized peer records without performing a network probe. It reports total peers, states, average and maximum observed latency, and the number requiring attention.

### Aggregate anomaly indicators

`server/telephony_anomaly_indicators.py` evaluates the exact aggregate outputs from `health_score()`, `summarize_calls()`, and `analyze_interconnects()`.

It produces six deterministic indicators:

- platform health score;
- answer rate;
- failure ratio;
- dominant failure concentration;
- interconnect attention ratio;
- interconnect latency.

Every indicator uses one of `ok`, `watch`, `critical`, or `insufficient_data`. Calls and interconnect indicators have fixed minimum sample gates. The evaluator rejects unknown fields, unsafe aggregate labels, customer-like identifiers, inconsistent totals, inconsistent score/state combinations, and invalid latency relationships.

The output deliberately omits carrier identifiers, countries, SIP codes, failure labels, component detail, and source maps. It contains only derived numeric values, fixed thresholds, static reason codes, and static same-page investigation anchors.

All safety fields are fixed false:

- automatic action;
- notification dispatch;
- traffic enforcement;
- route change;
- service control.

The thresholds are operational review defaults, not carrier SLAs, fraud findings, forecasts, root-cause diagnoses, or authority to act.

### Aggregate analytics console panels

The console renders three privacy-minimized panels:

- weighted platform health and normalized component states;
- aggregate call totals, answer rate, duration, and SIP failure classes;
- sanitized carrier utilization and aggregate interconnect states and latency.

The browser calls only:

```text
/api/telephony/analytics/health
/api/telephony/analytics/calls
/api/telephony/analytics/interconnects
```

`server/telephony_status_server.py` maps those exact same-origin routes to fixed loopback analytics API targets. It has no wildcard proxy, user-controlled target, browser access to port `8099`, or write method. Missing or invalid upstream data produces a bounded HTTP `503` response and an unavailable panel without breaking the existing console snapshot.

Template values are HTML-escaped before rendering. The carrier panel shows opaque sanitized identifiers and aggregate counts only; it does not assert carrier SLA, route readiness, or end-to-end interoperability.

### Report-generation audit events

`server/telephony_report_audit.py` records one canonical JSONL event after an aggregate report has already been produced.

The input and stored contracts are:

- `schemas/telephony/analytics-report-audit-input.schema.json`;
- `schemas/telephony/analytics-report-audit-event.schema.json`.

Each event contains only opaque event/report/generator IDs, UTC occurrence time, bounded report kind, repository revision, sanitized input-manifest hash, output-artifact hash, aggregate record count, a fixed privacy profile, and the previous/current event hashes.

The module:

- opens an absolute `.jsonl` path with `O_APPEND` and `O_NOFOLLOW`;
- requires an existing non-symlink parent directory and an owner-only regular file;
- locks the log before verification and append;
- validates every prior event and hash link;
- writes canonical ASCII JSON plus one newline;
- calls `fsync` before releasing the lock;
- rejects unknown fields, unbounded report kinds, unsafe IDs, invalid hashes, invalid timestamps, excessive counts, and any changed or malformed chain entry.

The audit chain is evidence of internal event integrity only. It does not establish report correctness, source completeness, lawful data access, carrier behavior, or production authorization.

## Privacy and evidence

Collectors and adapters must minimize data before it reaches the platform module.

- Prefer irreversible identifiers or internal record IDs over telephone numbers.
- Do not store authentication headers, secrets, SDP payloads, media, or message bodies.
- Keep synthetic fixtures clearly labeled.
- Preserve source timestamps and evidence references when reports are produced.
- Store operational records according to WW.CX retention and access policy.
- Treat CDR and signaling metadata as potentially sensitive even when content is absent.
- Reject unknown source fields until their privacy and operational purpose are documented.
- Do not connect a live data source merely because an offline adapter accepts its sanitized shape.
- Do not create fixture fallback values that could be mistaken for live aggregate analytics.
- Do not place report paths, titles, names, numbers, network addresses, route identifiers, or free-form metadata in audit events.
- Do not expose aggregate category labels through anomaly output when a bounded derived value is sufficient.

## Collector contract

A collector may create `CallEvent` records using only these fields:

- `direction`
- `disposition`
- `sip_code`
- `carrier_id`
- `destination_country`
- `duration_seconds`
- optional sanitized metadata

The delivered adapter contracts narrow optional metadata to adapter identity, schema version, opaque source record ID, UTC observation time, and SIP operational event type.

Collector-specific fields must remain outside the common aggregate unless they are documented, privacy-reviewed, and required for an approved operational purpose.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_console.py
python3 tests/validate_telephony_platform.py
python3 tests/validate_telephony_sanitized_adapters.py
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_telephony_report_audit.py
python3 tests/validate_telephony_anomaly_indicators.py
node --check src/web/telephony/telephony.js
```

The platform validation checks syntax, health scoring, SIP classification, call aggregation, interconnect aggregation, and required operational documentation.

The adapter validation checks canonical examples, bounded aliases, conservative SIP outcome derivation, batch failure behavior, schema markers, and negative cases for prohibited or privacy-bearing data. Repository CI also compiles the module and parses both JSON schemas and synthetic examples.

The console-panel validation imports the exact proxy route map, verifies fixed loopback targets and bounded `503` behavior, blocks arbitrary proxy and write markers, verifies browser isolation from port `8099`, and checks panel, escaping, accessibility, and unavailable-state markers.

The report-audit validation verifies canonical two-event append behavior, owner-only permissions, preserved prior bytes, full-chain validation, changed-content detection, incomplete-line rejection, symlink and broad-permission rejection, absolute-path enforcement, bounded schemas, and the absence of network, database, PBX, or service-control access paths.

The anomaly validation covers exact threshold boundaries, minimum sample gates, privacy leakage, aggregate consistency, fixed investigation anchors, and the absence of notification, network, database, service-control, or enforcement paths.

## Controlled follow-on

Completed read-only increments:

1. expose aggregate analytics through loopback-only GET endpoints;
2. add fail-closed offline sanitized CDR and SIP-event adapters;
3. complete authenticated live acceptance of the existing analytics service and runtime-source provenance;
4. add fixed same-origin analytics proxy routes and privacy-minimized console panels;
5. add append-only privacy-minimized report-generation audit events;
6. add conservative aggregate anomaly indicators with no automatic enforcement.

The following work can continue within a read-only implementation branch:

1. document separately reviewed Asterisk AMI/ARI, Kamailio/OpenSIPS, RTPengine, and messaging source-minimization boundaries;
2. design live source collectors only after access, privacy, retention, and rollback review;
3. design a report generator and runtime audit retention model without deploying them;
4. design a read-only anomaly API and console presentation without deploying them;
5. prepare a bounded console deployment and live-verification runbook without executing it.

Any write capability must use a separate staged control plane:

```text
propose -> inspect -> validate -> approve/reject -> apply -> verify -> rollback
```

A future write plane requires explicit action-level authorization, strong identity separation, immutable audit evidence, bounded configuration schemas, and dedicated negative tests. It must not be added to the browser or this analytics module.
