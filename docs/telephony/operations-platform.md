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
                  read-only collectors
                         |
             normalized sanitized records
                         |
          server/telephony_platform.py
                 |                 |
          health analysis      call analysis
                 |                 |
          loopback API / console / reports
```

The browser must continue to use the localhost-only server boundary. It must never connect directly to PBX, carrier, SBC, media, or database administration interfaces.

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

## Collector contract

A collector may create `CallEvent` records using only these fields:

- `direction`
- `disposition`
- `sip_code`
- `carrier_id`
- `destination_country`
- `duration_seconds`
- optional sanitized metadata

Collector-specific fields must remain outside the common aggregate unless they are documented, privacy-reviewed, and required for an approved operational purpose.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_console.py
python3 tests/validate_telephony_platform.py
```

The second command validates syntax, health scoring, SIP classification, call aggregation, interconnect aggregation, and required operational documentation.

## Controlled follow-on

The following work can continue within a read-only implementation branch:

1. integrate sanitized CDR adapters;
2. expose aggregate analytics through loopback-only GET endpoints;
3. add console panels for failure classes, carrier performance, and health scoring;
4. add append-only audit records for report generation;
5. add anomaly detection with conservative thresholds and no automatic enforcement;
6. document Asterisk AMI/ARI, Kamailio/OpenSIPS, RTPengine, and messaging adapters.

Any write capability must use a separate staged control plane:

```text
propose -> inspect -> validate -> approve/reject -> apply -> verify -> rollback
```

A future write plane requires explicit action-level authorization, strong identity separation, immutable audit evidence, bounded configuration schemas, and dedicated negative tests. It must not be added to the browser or this analytics module.
