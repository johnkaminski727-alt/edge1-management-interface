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
- generate operator-facing recommendations from already-authorized data.

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
          loopback API / console / reports
```

The browser must continue to use the localhost-only server boundary. It must never connect directly to PBX, carrier, SBC, media, or database administration interfaces.

The sanitized adapter library is not a live collector. It performs no file, network, database, credential, service-control, PBX, carrier, route, or configuration access.

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
```

The platform validation checks syntax, health scoring, SIP classification, call aggregation, interconnect aggregation, and required operational documentation.

The adapter validation checks canonical examples, bounded aliases, conservative SIP outcome derivation, batch failure behavior, schema markers, and negative cases for prohibited or privacy-bearing data. Repository CI also compiles the module and parses both JSON schemas and synthetic examples.

## Controlled follow-on

Completed read-only increments:

1. expose aggregate analytics through loopback-only GET endpoints;
2. add fail-closed offline sanitized CDR and SIP-event adapters;
3. complete authenticated live acceptance of the existing analytics service and runtime-source provenance.

The following work can continue within a read-only implementation branch:

1. add console panels for health score, failure classes, and carrier performance;
2. add append-only audit records for report generation;
3. add anomaly detection with conservative thresholds and no automatic enforcement;
4. document separately reviewed Asterisk AMI/ARI, Kamailio/OpenSIPS, RTPengine, and messaging source-minimization boundaries;
5. design live source collectors only after access, privacy, retention, and rollback review.

Any write capability must use a separate staged control plane:

```text
propose -> inspect -> validate -> approve/reject -> apply -> verify -> rollback
```

A future write plane requires explicit action-level authorization, strong identity separation, immutable audit evidence, bounded configuration schemas, and dedicated negative tests. It must not be added to the browser or this analytics module.
