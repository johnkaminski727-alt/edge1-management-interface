# Emergency Services Standard

## Purpose

Define the minimum engineering, operational, evidence, and change controls for any WW.CX service that may originate, route, modify, relay, or support emergency calls.

## Activation boundary

Emergency calling MUST remain disabled or explicitly marked unavailable until the applicable service model, jurisdiction, provider arrangements, customer disclosures, address procedures, routing, testing, monitoring, escalation, and evidence requirements are complete. A successful ordinary call test is not evidence of emergency-service readiness.

## Source of truth

Maintain a controlled emergency-services register containing service identifiers, telephone numbers, customer or site association, validated service address, provider, jurisdiction, routing model, activation state, test evidence, last reconciliation time, exceptions, and accountable owner.

## Address controls

- Collect only the address information required for the applicable service.
- Validate and normalize addresses through the approved provider or authoritative process before activation.
- Prevent activation when required address data is missing, rejected, stale, or ambiguous.
- Record effective times and preserve prior values for audit and incident reconstruction.
- Apply explicit procedures for nomadic, multi-location, softphone, and temporary-use services.

## Routing and fail-safe behavior

Emergency traffic MUST use an approved route that is isolated from ordinary least-cost routing. Routing policy MUST define primary and alternate paths, timeout behavior, location-data treatment, caller identity, failure escalation, and the conditions under which service is blocked rather than sent with unreliable information.

Do not silently reroute emergency traffic through an unapproved ordinary carrier path. Failures MUST generate immediate operational alerts and preserve evidence without exposing sensitive location information more broadly than necessary.

## Testing

Testing MUST use provider-approved test procedures and numbers. Never place a live emergency call merely to test configuration. Before activation, validate signaling, identity, address association, routing selection, provider acknowledgement, monitoring, and escalation. Record the test case, time, participants, expected result, actual result, provider reference, and cleanup actions.

## Monitoring

Monitor route availability, provider health, address-validation failures, rejected updates, unexpected route selection, call failures, and stale records. Alert thresholds and escalation paths MUST be documented and exercised.

## Customer and operator safeguards

Applicable notices, limitations, address-update duties, power and Internet dependencies, nomadic-use constraints, and escalation contacts MUST be communicated through approved customer-facing materials. Operators MUST have a concise incident runbook and access to the authoritative service and address records needed for escalation.

## Change control

Any change affecting emergency routing, address data, provider integration, caller identity, SBC behavior, DNS, certificates, firewalls, numbering, or failover is a high-impact change. Require an approved change record, peer review, rollback plan, maintenance window where appropriate, and post-change validation.

## Incident response

Treat suspected misrouting, missing or incorrect address data, blocked emergency traffic, provider rejection, unauthorized changes, and unexplained emergency-call failures as critical incidents. Freeze non-essential changes, preserve logs and configuration evidence, escalate to the applicable provider and internal authority, reconcile affected records, and document corrective and preventive actions.

## Evidence and review

Preserve provider agreements and references, architecture decisions, activation approvals, address-validation evidence, test records, monitoring evidence, incident reports, reconciliation records, and customer-notice versions according to the evidence-management standard. Review the complete emergency-services posture at least annually and before any material launch expansion.