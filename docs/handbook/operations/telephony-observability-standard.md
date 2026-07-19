# Telephony Observability Standard

## Purpose

Define the minimum telemetry, alerting, retention, and evidence controls required to operate WW.CX voice, messaging, numbering, interconnect, and supporting services safely.

## Principles

Observability MUST distinguish service availability, signaling health, media quality, delivery state, customer impact, and data freshness. Dashboards are operational views, not authoritative evidence unless their source, query, time range, and export are preserved.

## Required coverage

Collect and correlate, where applicable:

- service and process health;
- listener and dependency readiness;
- SIP registration, OPTIONS, transaction, response-code, and dialog metrics;
- call attempts, completions, failures, duration, direction, and route selection;
- media establishment, packet loss, jitter, latency, and one-way-audio indicators;
- messaging acceptance, queue depth, retries, delivery receipts, suppression, and failure classes;
- numbering dataset age, import results, reconciliation exceptions, and assignment conflicts;
- certificate, DNS, database, storage, queue, and clock health;
- emergency-service integration and address-validation failures;
- authentication, authorization, administrative changes, and unusual traffic patterns.

## Data handling

Telemetry MUST minimize message content, call content, credentials, and unnecessary personal information. Use stable correlation identifiers instead of exposing sensitive payloads. Access, retention, export, and deletion rules MUST align with privacy, security, contractual, and evidence requirements.

## Metrics and labels

Metric names and labels MUST be documented, bounded, and resistant to uncontrolled cardinality. Do not use full telephone numbers, addresses, message bodies, SIP headers containing secrets, or customer identifiers as unrestricted metric labels.

## Logs and traces

Structured logs SHOULD include timestamp, service, environment, event type, severity, actor or system identity, request or correlation ID, outcome, and safe error context. Clock synchronization is mandatory. Redaction MUST occur before storage or export where practical.

## Alerting

Alerts MUST identify the affected service, symptom, severity, first observed time, evidence link, owner, and initial runbook. Alert on customer-impacting failure, emergency-service risk, interconnect loss, sustained registration or delivery failure, queue growth, data staleness, certificate expiry, unauthorized change, and evidence-pipeline failure.

Avoid paging solely on noisy single samples. Use sustained thresholds, rate changes, dependency context, and maintenance suppression where appropriate. Every paging alert MUST have an owner and response expectation.

## Dashboards

Maintain role-appropriate dashboards for executive posture, NOC operations, carrier interconnect, voice quality, messaging, numbering, public safety, security, and platform dependencies. Clearly label simulated, fixture, stale, degraded, disabled, or unavailable data.

## Synthetic tests

Synthetic probes MUST use controlled identifiers and approved destinations. They must not create misleading customer, carrier, numbering, or emergency-service records. Record the probe source, expected path, schedule, success criteria, and cleanup behavior.

## Incident evidence

During incidents, preserve relevant logs, metrics, traces, configuration versions, route decisions, provider references, timestamps, and operator actions. Record known telemetry gaps rather than inferring missing results.

## Review

Review alert quality, false positives, missed incidents, retention, access, dashboard ownership, metric cardinality, and runbook accuracy regularly. Treat blind spots in emergency calling, interconnect, authentication, or customer-impacting delivery as launch or change blockers.