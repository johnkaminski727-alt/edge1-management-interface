# Big Bird Telephony Operations

## Status

Phase 1 is a read-only, fixture-backed operational console for SIP, PBX, SMS/MMS, media, numbering, and carrier interconnect visibility. It deliberately exposes no production-changing controls.

The consolidated management and analytics foundation is documented in [Edge1 Telephony Operations Platform](operations-platform.md). Project delivery and controlled blockers are tracked in the [WW.CX Telephony Operations Platform Register](../project-register/wwcx-telephony-operations-platform.md).

## Preview

From the repository root:

```bash
python3 -m http.server 8088 --directory src/web
```

Open `http://127.0.0.1:8088/telephony/` through an approved local or private connection.

## Current surfaces

- overall network posture and summary metrics
- PBX, SIP edge, messaging, media relay, numbering, and carrier service health
- carrier and trunk OPTIONS-style health summaries
- SIP endpoint registration posture
- active alert feed
- responsive desktop and mobile layouts
- sanitized offline fixture fallback
- normalized health scoring and privacy-minimized aggregate analytics foundation
- SIP failure classification and interconnect summaries

## Adapter boundary

Production collectors must emit the normalized snapshot described by `src/api/telephony_status_contract.json`. Planned read-only adapters include Asterisk AMI/ARI, FreeSWITCH ESL, Kamailio/OpenSIPS RPC or database views, RTPengine statistics, messaging-gateway queues, numbering inventory, sanitized CDR sources, and controlled SIP OPTIONS probes.

Adapters must not expose credentials, message bodies, audio payloads, authentication secrets, or unredacted customer records. Public repository fixtures must remain synthetic.

The shared analytics model in `server/telephony_platform.py` accepts only sanitized aggregate inputs and contains no service-control, configuration, call-origination, carrier, routing, or number-management write path.

## Safety model

Phase 1 is read-only. Future configuration changes must use the existing staged workflow:

```text
propose -> inspect -> validate -> approve/reject -> operator-controlled apply -> verify/rollback
```

The browser must never connect directly to PBX, carrier, or gateway administrative interfaces. A localhost-only API wrapper will normalize and redact approved data sources.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_console.py
python3 tests/validate_telephony_platform.py
```

## Operator acceptance

Before treating the console as accepted for operational use, complete the [Telephony Console Operator Acceptance Checklist](operator-acceptance-checklist.md). The checklist requires repository validation, loopback-only verification, read-only behavior checks, explicit integration evidence, stop conditions, and an acceptance record.

Checklist completion does not authorize production routing, public exposure, emergency-calling changes, carrier administration, or write controls.

## Next implementation slice

1. expose aggregate health, call, and interconnect analytics through loopback-only GET endpoints
2. add sanitized CDR and SIP-event collectors
3. add health-score, failure-class, and carrier-performance console panels
4. add append-only report-generation audit events
5. add bounded anomaly indicators without automatic enforcement
6. complete Edge1 validation, smoke tests, evidence capture, and deployment runbook updates
