# Big Bird Telephony Operations

## Status

Phase 1 is a read-only, fixture-backed operational console for SIP, PBX, SMS/MMS, media, numbering, and carrier interconnect visibility. It deliberately exposes no production-changing controls.

The consolidated management and analytics foundation is documented in [Edge1 Telephony Operations Platform](operations-platform.md). Project delivery and controlled blockers are tracked in the [WW.CX Telephony Operations Platform Register](../project-register/wwcx-telephony-operations-platform.md). DTMF capability inventory and its controlled test boundary are documented in [Asterisk DTMF Readiness](dtmf-readiness.md). The authenticated Edge1 DTMF result is recorded in [Asterisk DTMF Readiness Live Acceptance — 2026-08-01](asterisk-dtmf-readiness-live-acceptance-20260801.md). Endpoint-policy reconciliation is documented in [Asterisk PJSIP Endpoint Policy Reconciliation](pjsip-endpoint-policy-reconciliation.md), with the authenticated result recorded in [Asterisk PJSIP Endpoint Policy Live Acceptance — 2026-08-01](asterisk-pjsip-endpoint-policy-live-acceptance-20260801.md). Provider claims must pass the privacy-safe [DTMF Provider Evidence Intake](dtmf-provider-evidence-intake.md) before promotion into the capability matrix.

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
- read-only Asterisk DTMF policy inventory and offline complete 16-key signal validation
- sanitized reconciliation of runtime PJSIP object counts against generated endpoint-policy records
- evidence-gated provider capability intake that rejects unsupported or privacy-bearing claims

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

The DTMF readiness and endpoint-policy reconciliation audits perform no call or channel creation, no tone or SIP request transmission, no database query, and no endpoint, trunk, route, carrier, or emergency-calling change. The provider evidence intake does not contact providers or authorize a live test. Carrier interoperability remains unknown until supported by provider-specific technical documentation or a separately authorized controlled test.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_console.py
python3 tests/validate_telephony_platform.py
python3 tests/validate_asterisk_dtmf_readiness_audit.py
python3 tests/validate_asterisk_pjsip_endpoint_policy_reconciliation.py
python3 tests/test_validate_dtmf_provider_evidence.py
python3 tools/telephony/validate_dtmf_provider_evidence.py \
  examples/telephony/dtmf-provider-evidence.example.json
```

## Operator acceptance

Before treating the console as accepted for operational use, complete the [Telephony Console Operator Acceptance Checklist](operator-acceptance-checklist.md). The checklist requires repository validation, loopback-only verification, read-only behavior checks, explicit integration evidence, stop conditions, and an acceptance record.

Checklist completion does not authorize production routing, public exposure, emergency-calling changes, carrier administration, or write controls.

The authenticated DTMF audit completed on `edge1.ww.cx` with exit code `0`, one warning, zero failures, all sixteen offline keypad symbols passing, and no runtime mutation. The subsequent PJSIP reconciliation completed with exit code `0`, two informational warnings, zero failures, and consistent zero endpoint counts across runtime and 23 generated configuration files. Local Asterisk capability is accepted. Carrier, endpoint, trunk, SIP INFO, in-band, SDP-negotiation, and end-to-end behavior remain `unverified`.

## Next implementation slice

1. use the sanitized evidence-intake record for each genuine provider and route candidate
2. obtain provider-specific RFC 4733, event-range, SIP INFO, in-band, codec, and extended-key documentation
3. populate the carrier capability matrix only from records that pass evidence validation
4. leave unsupported or undocumented carrier capabilities as `unknown`
5. keep every live route and interconnect marked `unverified` pending separate controlled-test authorization
6. expose aggregate health, call, and interconnect analytics through loopback-only GET endpoints
7. add sanitized CDR and SIP-event collectors
8. add health-score, failure-class, and carrier-performance console panels
9. add append-only report-generation audit events
10. add bounded anomaly indicators without automatic enforcement
11. complete remaining Edge1 validation, smoke tests, evidence capture, and deployment runbook updates
