# Big Bird Telephony Operations

## Status

Phase 1 is a read-only, fixture-backed operational console for SIP, PBX, SMS/MMS, media, numbering, and carrier interconnect visibility. It deliberately exposes no production-changing controls.

The consolidated management and analytics foundation is documented in [Edge1 Telephony Operations Platform](operations-platform.md). Project delivery and controlled blockers are tracked in the [WW.CX Telephony Operations Platform Register](../project-register/wwcx-telephony-operations-platform.md). DTMF capability inventory and its controlled test boundary are documented in [Asterisk DTMF Readiness](dtmf-readiness.md). The authenticated Edge1 DTMF result is recorded in [Asterisk DTMF Readiness Live Acceptance — 2026-08-01](asterisk-dtmf-readiness-live-acceptance-20260801.md). Endpoint-policy reconciliation is documented in [Asterisk PJSIP Endpoint Policy Reconciliation](pjsip-endpoint-policy-reconciliation.md), with the authenticated result recorded in [Asterisk PJSIP Endpoint Policy Live Acceptance — 2026-08-01](asterisk-pjsip-endpoint-policy-live-acceptance-20260801.md). Provider claims must pass the privacy-safe [DTMF Provider Evidence Intake](dtmf-provider-evidence-intake.md) before promotion into the capability matrix; the authenticated host result is recorded in [DTMF Provider-Public Evidence Live Acceptance — 2026-08-01](dtmf-provider-public-evidence-live-acceptance-20260801.md). Aggregate analytics repository acceptance is recorded in [Telephony Analytics Acceptance Record](analytics-acceptance-record.md), with the authenticated Edge1 result in [Telephony Analytics Live Acceptance — 2026-08-01](telephony-analytics-live-acceptance-20260801.md). Offline sanitized CDR and SIP outcome normalization is documented in [Sanitized Telephony Event Adapters](sanitized-event-adapters.md). The read-only aggregate console presentation is documented in [Telephony Analytics Console Panels](analytics-console-panels.md). Hash-chained report-generation evidence is documented in [Telephony Analytics Report Audit Events](analytics-report-audit-events.md). Offline deterministic report creation is documented in [Telephony Aggregate Report Generator](aggregate-report-generator.md), with repository acceptance in [Telephony Aggregate Report Generator Repository Acceptance — 2026-08-01](aggregate-report-generator-repository-acceptance-20260801.md). Conservative informational anomaly evaluation is documented in [Telephony Aggregate Anomaly Indicators](anomaly-indicators.md), with repository acceptance in [Telephony Anomaly Indicator Repository Acceptance — 2026-08-01](anomaly-indicator-repository-acceptance-20260801.md) and authenticated live deployment in [Telephony Anomaly API and Console Panel Live Acceptance — 2026-08-01](telephony-anomaly-api-panel-live-acceptance-20260801.md).

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
- loopback-only aggregate health, anomaly, call-summary, and interconnect-summary GET endpoints on port `8099`
- fixed same-origin read routes for aggregate analytics through the loopback console
- console panels for health score, call and SIP outcomes, failure classes, sanitized carrier utilization, aggregate interconnect posture, and informational anomaly indicators
- fail-closed offline adapters for already-sanitized CDR and SIP outcome records
- append-only, owner-only, hash-chained JSONL audit events for aggregate report generation
- deterministic offline JSON and Markdown report bundles with owner-only output, SHA-256 manifests, and review-only audit-event candidates
- deterministic aggregate-only anomaly indicators with fixed thresholds, minimum-sample gates, and no automatic action
- SIP failure classification and interconnect summaries
- read-only Asterisk DTMF policy inventory and offline complete 16-key signal validation
- sanitized reconciliation of runtime PJSIP object counts against generated endpoint-policy records
- evidence-gated provider capability intake that rejects unsupported or privacy-bearing claims
- protected analytics and anomaly live-acceptance audits with runtime-source provenance checks

## Adapter boundary

Production collectors must emit the normalized snapshot described by `src/api/telephony_status_contract.json`. Planned read-only source integrations include Asterisk AMI/ARI, FreeSWITCH ESL, Kamailio/OpenSIPS RPC or approved views, RTPengine statistics, messaging-gateway queues, numbering inventory, and controlled SIP OPTIONS observations.

The repository includes offline fail-closed adapters in `server/telephony_sanitized_adapters.py` for inputs that have already been minimized. Canonical contracts are defined by:

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

The analytics console panels use only fixed same-origin paths. The console server maps them to fixed loopback analytics endpoints. There is no arbitrary proxy, direct browser access to port `8099`, write method, or fixture fallback that fabricates aggregate analytics.

The report-audit module records only opaque identifiers, timestamps, repository and artifact hashes, aggregate count, a fixed privacy profile, and hash-chain fields. It does not generate reports, read telephony sources, create runtime directories, or activate a job or service.

The aggregate report generator consumes only the accepted health, call, and interconnect summaries. It recomputes the informational anomaly contract and creates one new owner-only JSON/Markdown bundle plus an audit-event candidate and SHA-256 manifest. It never overwrites an artifact, appends a live audit log, contacts a service, reads a live source, creates a scheduler, or activates a retention policy.

The anomaly evaluator consumes only the accepted aggregate health, call-summary, and interconnect-summary contracts. It emits bounded informational states and static investigation anchors only. It does not access live sources, dispatch notifications, block traffic, change routes, control services, or perform automatic remediation.

The accepted anomaly deployment refreshed the canonical console process once and restarted the analytics service once under a rollback-protected procedure. Both services remain `wwadmin`-owned, loopback-only, and read-only. The live audit verified canonical source provenance, the same-origin anomaly contract, POST rejection, payload privacy, clean repository state, and preserved Git-index ownership. It did not access a live telephony source or perform a call, message, DTMF, routing, carrier, database, credential, firewall, DNS, certificate, authentication, or public-listener action.

## Validation

From the repository root:

```bash
python3 tests/validate_telephony_console.py
python3 tests/validate_telephony_platform.py
python3 tests/validate_telephony_analytics_api.py
python3 tests/validate_telephony_analytics_live_acceptance_audit.py
python3 tests/validate_telephony_sanitized_adapters.py
python3 tests/validate_telephony_analytics_console_panels.py
python3 tests/validate_telephony_report_audit.py
python3 tests/validate_telephony_aggregate_report.py
python3 tests/validate_telephony_anomaly_indicators.py
python3 tests/validate_telephony_anomaly_api_panel.py
python3 tests/validate_telephony_anomaly_live_deployment.py
python3 tests/validate_telephony_anomaly_console_refresh.py
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

The aggregate analytics service is accepted on Edge1 as a loopback-only read-only surface. The authenticated audit confirmed active and enabled service state, port `8099`, GET payload and privacy contracts, POST rejection, matching runtime and canonical source hashes, zero warnings, zero failures, preserved repository-index ownership, and no unauthorized telephony or infrastructure mutation.

The aggregate console panels and informational anomaly evaluator are live-accepted on Edge1. The corrected deployment refreshed the console process so its canonical same-origin route map became active, moved analytics runtime execution to canonical `main`, and passed the complete source-provenance, listener, endpoint, anomaly-contract, privacy, method-boundary, and repository-safety audit. The console and analytics services remain private on `127.0.0.1:8096` and `127.0.0.1:8099`. This acceptance does not authorize live collectors, database access, carrier integration, routing, calls, DTMF, notifications, enforcement, or public exposure.

The report-audit and aggregate report-generator foundations are repository-complete. The generator creates only new owner-only offline bundles and emits an unappended audit-event candidate. No live report service, timer, protected runtime directory, retention policy, automatic audit append, source collection, or runtime deployment is accepted yet.

## Next implementation slice

1. keep live CDR, AMI/ARI, SIP-edge, log, packet, and carrier source connections blocked pending separate design and access review
2. use the sanitized evidence-intake record for each genuine provider and route candidate
3. obtain provider-specific RFC 4733, event-range, SIP INFO, in-band, codec, and extended-key documentation
4. populate the carrier capability matrix only from records that pass evidence validation
5. leave unsupported or undocumented carrier capabilities as `unknown`
6. keep every live route and interconnect marked `unverified` pending separate controlled-test authorization
7. design a separately reviewed protected report runtime directory, retention policy, automatic audit-append gate, scheduler, and deployment plan
8. complete remaining Edge1 validation, evidence capture, and deployment runbook updates
