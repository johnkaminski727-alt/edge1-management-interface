# Big Bird Telephony Operations

## Status

Phase 1 is a read-only, fixture-backed operational console for SIP, PBX, SMS/MMS, media, numbering, and carrier interconnect visibility. It deliberately exposes no production-changing controls.

The consolidated management and analytics foundation is documented in [Edge1 Telephony Operations Platform](operations-platform.md). Project delivery and controlled blockers are tracked in the [WW.CX Telephony Operations Platform Register](../project-register/wwcx-telephony-operations-platform.md). DTMF capability inventory and its controlled test boundary are documented in [Asterisk DTMF Readiness](dtmf-readiness.md). The authenticated Edge1 DTMF result is recorded in [Asterisk DTMF Readiness Live Acceptance — 2026-08-01](asterisk-dtmf-readiness-live-acceptance-20260801.md). Endpoint-policy reconciliation is documented in [Asterisk PJSIP Endpoint Policy Reconciliation](pjsip-endpoint-policy-reconciliation.md), with the authenticated result recorded in [Asterisk PJSIP Endpoint Policy Live Acceptance — 2026-08-01](asterisk-pjsip-endpoint-policy-live-acceptance-20260801.md). Provider claims must pass the privacy-safe [DTMF Provider Evidence Intake](dtmf-provider-evidence-intake.md) before promotion into the capability matrix; the authenticated host result is recorded in [DTMF Provider-Public Evidence Live Acceptance — 2026-08-01](dtmf-provider-public-evidence-live-acceptance-20260801.md). Aggregate analytics repository acceptance is recorded in [Telephony Analytics Acceptance Record](analytics-acceptance-record.md), with the authenticated Edge1 result in [Telephony Analytics Live Acceptance — 2026-08-01](telephony-analytics-live-acceptance-20260801.md). Offline sanitized CDR and SIP outcome normalization is documented in [Sanitized Telephony Event Adapters](sanitized-event-adapters.md). The read-only aggregate console presentation is documented in [Telephony Analytics Console Panels](analytics-console-panels.md).

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
- loopback-only aggregate health, call-summary, and interconnect-summary GET endpoints on port `8099`
- fixed same-origin read routes for aggregate analytics through the loopback console
- console panels for health score, call and SIP outcomes, failure classes, sanitized carrier utilization, and aggregate interconnect posture
- SIP failure classification and interconnect summaries
- fail-closed offline adapters for already-sanitized CDR and SIP outcome records
- read-only Asterisk DTMF policy inventory and offline complete 16-key signal validation
- sanitized reconciliation of runtime PJSIP object counts against generated endpoint-policy records
- evidence-gated provider capability intake that rejects unsupported or privacy-bearing claims
- protected, non-mutating analytics live-acceptance audit with runtime-source provenance checks

## Adapter boundary

Production collectors must emit the normalized snapshot described by `src/api/telephony_status_contract.json`. Planned read-only source integrations include Asterisk AMI/ARI, FreeSWITCH ESL, Kamailio/OpenSIPS RPC or approved views, RTPengine statistics, messaging-gateway queues, numbering inventory, and controlled SIP OPTIONS observations.

The repository now includes offline fail-closed adapters in `server/telephony_sanitized_adapters.py` for inputs that have already been minimized. Canonical contracts are defined by:

- `schemas/telephony/sanitized-cdr-record.schema.json`
- `schemas/telephony/sanitized-sip-event.schema.json`

Adapters reject unknown fields, telephone-like identifiers, SIP URIs, IP and email addresses, caller/callee fields, headers, credentials, SDP, recordings, message bodies, names, and nested free-form metadata. They perform no file, database, network, credential, service-control, PBX, carrier, route, or configuration access.

Production collectors must not expose credentials, message bodies, audio payloads, authentication secrets, or unredacted customer records. Public repository fixtures must remain synthetic. Connecting any live source remains a separate reviewed operation.

The shared analytics model in `server/telephony_platform.py` accepts only sanitized aggregate inputs and contains no service-control, configuration, call-origination, carrier, routing, or number-management write path.

## Safety model

Phase 1 is read-only. Future configuration changes must use the existing staged workflow:

```text
propose -> inspect -> validate -> approve/reject -> operator-controlled apply -> verify/rollback
```

The browser must never connect directly to PBX, carrier, or gateway administrative interfaces. A localhost-only API wrapper normalizes and redacts approved data sources.

The DTMF readiness and endpoint-policy reconciliation audits perform no call or channel creation, no tone or SIP request transmission, no database query, and no endpoint, trunk, route, carrier, or emergency-calling change. The provider evidence intake does not contact providers or authorize a live test. Carrier interoperability remains unknown until supported by provider-specific technical documentation or a separately authorized controlled test.

The telephony analytics live-acceptance audit does not install, enable, start, stop, restart, or reload the analytics service. It inspects the existing service, loopback listener, read-only method boundary, aggregate payload contract, privacy boundary, runtime-source provenance, and repository-index ownership only.

The sanitized event adapters do not activate a collector or read any live source. They only normalize synthetic or independently sanitized mappings supplied by an approved caller.

The analytics console panels use only three exact same-origin paths. The console server maps them to three fixed loopback analytics endpoints. There is no arbitrary proxy, direct browser access to port `8099`, write method, or fixture fallback that fabricates aggregate analytics.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_console.py
python3 tests/validate_telephony_platform.py
python3 tests/validate_telephony_analytics_api.py
python3 tests/validate_telephony_analytics_live_acceptance_audit.py
python3 tests/validate_telephony_sanitized_adapters.py
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_asterisk_dtmf_readiness_audit.py
python3 tests/validate_asterisk_pjsip_endpoint_policy_reconciliation.py
python3 tests/test_validate_dtmf_provider_evidence.py
python3 tools/telephony/validate_dtmf_provider_evidence.py \
  examples/telephony/dtmf-provider-evidence.example.json
```

## Operator acceptance

Before treating the console as accepted for operational use, complete the [Telephony Console Operator Acceptance Checklist](operator-acceptance-checklist.md). The checklist requires repository validation, loopback-only verification, read-only behavior checks, explicit integration evidence, stop conditions, and an acceptance record.

Checklist completion does not authorize production routing, public exposure, emergency-calling changes, carrier administration, or write controls.

The authenticated DTMF audit completed on `edge1.ww.cx` with exit code `0`, one warning, zero failures, all sixteen offline keypad symbols passing, and no runtime mutation. The subsequent PJSIP reconciliation completed with exit code `0`, two informational warnings, zero failures, and consistent zero endpoint counts across runtime and 23 generated configuration files. Local Asterisk capability is accepted.

The provider-public evidence package was subsequently synchronized and validated on Edge1 with a clean repository, stable `wwadmin:wwadmin` index ownership, unchanged service state, and a checksum-backed protected evidence bundle. The account-level automatic in-band fallback is documented. RFC 4733 event range, SIP INFO, extended `A-D`, codec and transcoding behavior, exact directionality, carrier-route behavior, and end-to-end interoperability remain unknown or unverified. No live test is authorized.

The aggregate analytics service is accepted on Edge1 as a loopback-only read-only surface. The authenticated audit confirmed active and enabled service state, port `8099`, GET payload and privacy contracts, POST rejection, matching runtime and canonical source hashes, zero warnings, zero failures, preserved repository-index ownership, and no runtime mutation. This acceptance does not authorize live collectors, database access, carrier integrations, routing, calls, DTMF, or public exposure.

The aggregate console panels are repository-complete but are not yet deployed to the running console service. Deployment requires a separate bounded operator action and live verification of the console source, same-origin routes, listener scope, and rendered unavailable-state behavior.

## Next implementation slice

1. keep live CDR, AMI/ARI, SIP-edge, log, and carrier source connections blocked pending separate design and access review
2. add append-only report-generation audit events
3. add bounded anomaly indicators without automatic enforcement
4. use the sanitized evidence-intake record for each genuine provider and route candidate
5. obtain provider-specific RFC 4733, event-range, SIP INFO, in-band, codec, and extended-key documentation
6. populate the carrier capability matrix only from records that pass evidence validation
7. leave unsupported or undocumented carrier capabilities as `unknown`
8. keep every live route and interconnect marked `unverified` pending separate controlled-test authorization
9. perform a separately authorized bounded console deployment and capture protected live evidence
10. complete remaining Edge1 validation, evidence capture, and deployment runbook updates
