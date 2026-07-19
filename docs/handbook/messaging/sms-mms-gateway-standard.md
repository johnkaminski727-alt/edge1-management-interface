# SMS and MMS Gateway Engineering Standard

## Purpose

Define the safe architecture and operating controls for WW.CX messaging services while preserving a clear boundary between tested software, carrier integration, and live customer service.

## Service boundary

The messaging gateway MUST remain logically separate from Asterisk, FreePBX, carrier SIP signaling, and customer management systems. Integration MUST occur through authenticated, documented interfaces. A messaging failure MUST NOT impair voice routing.

## Core components

A production design SHOULD include:

- provider adapters for inbound and outbound carrier protocols;
- normalized message and delivery-event models;
- durable queues with idempotent processing;
- consent, suppression, and keyword policy enforcement;
- MMS object quarantine, validation, and controlled storage;
- delivery receipts and correlation identifiers;
- authenticated customer and operations APIs;
- rate limiting, abuse controls, and fraud detection;
- metrics, audit events, backup, and recovery procedures.

## Message lifecycle

Every message MUST have a traceable state transition such as accepted, validated, queued, submitted, delivered, failed, expired, quarantined, or suppressed. State changes MUST be idempotent and retain the provider event identifier and internal correlation identifier.

Duplicate inbound events MUST NOT create duplicate customer messages or outbound actions. Retry policy MUST distinguish temporary failures from permanent rejection.

## Consent and suppression

- STOP and equivalent opt-out requests MUST be processed promptly and idempotently.
- START or equivalent restoration MUST follow the applicable program rules and retained consent evidence.
- HELP responses MUST identify the service and a support path without exposing internal information.
- Suppression MUST be enforced before provider submission, not only at the user interface.
- Administrative overrides MUST require authorization, reason, audit evidence, and applicable legal review.

## MMS handling

Inbound media MUST be treated as untrusted. The system MUST enforce size, type, fetch-time, redirect, and storage limits; quarantine unexpected content; and avoid executing or rendering active content in privileged contexts. Retention and deletion policy MUST account for privacy, customer expectations, legal holds, and provider expiry.

## Security

- Separate read-only monitoring credentials from control credentials.
- Validate provider signatures, timestamps, replay windows, and source policy.
- Store secrets only in approved secret-management mechanisms.
- Require actor and reason for operational control actions.
- Restrict public webhook endpoints to the minimum required methods and payload sizes.
- Do not log full message content by default; use redacted identifiers and bounded diagnostic sampling.

## Reliability

The gateway MUST use durable persistence for accepted work, bounded retries with backoff, dead-letter handling, queue-depth alerts, and reconciliation between internal state and provider receipts. Backpressure MUST protect the database and provider connection rather than dropping accepted messages silently.

## Monitoring

Monitor availability, database readiness, queue age, queue depth, submission latency, provider acceptance rate, delivery rate, failure classes, duplicate events, suppression events, webhook authentication failures, MMS quarantine, and control actions.

A service shown as critical because it is intentionally not activated MUST be labelled as inactive or not configured rather than creating a false production incident.

## Activation gates

Live carrier activation requires:

- selected provider and executed commercial terms;
- approved sender and campaign registration where applicable;
- verified webhook authentication and replay protection;
- consent and suppression review;
- privacy and retention review;
- non-production DID testing;
- monitoring, backup, restore, and incident-response evidence;
- customer support and abuse-handling procedures;
- explicit production change approval.

## Rollback

Rollback SHOULD pause new submissions safely, retain accepted work, prevent duplicate resubmission, preserve delivery evidence, and permit controlled reconciliation after service restoration.