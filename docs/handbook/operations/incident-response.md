# Telecommunications Incident Response

## Priorities

1. Protect life-safety and emergency-calling functions.
2. Contain security or fraud exposure.
3. Restore stable service.
4. Preserve evidence.
5. Communicate accurately.

## Severity guide

- SEV-1: emergency-calling impairment, widespread outage, active compromise, or uncontrolled toll fraud.
- SEV-2: significant service degradation, regional failure, or material customer impact.
- SEV-3: limited degradation with a viable workaround.
- SEV-4: low-impact defect or operational request.

## First response

- Assign an incident commander and scribe.
- Record start time, detection source, affected services, and current symptoms.
- Freeze unrelated production changes.
- Check SBC, SIP proxy, PBX, carrier, DNS, certificate, media, database, and network health.
- Preserve relevant logs before rotation or restart.
- Avoid exposing credentials or customer content in tickets and chat.

## Communications

Use confirmed facts, scope, mitigation status, and the next update point. Do not speculate about root cause. Escalate emergency-services, privacy, lawful-access, and regulatory implications to qualified personnel.

## Recovery validation

Confirm call setup, two-way media, DTMF, caller identity, failover, CDR generation, monitoring recovery, and any affected messaging paths.

## Closure

Create a post-incident review with timeline, impact, root cause, contributing factors, corrective actions, owners, due dates, and links to preserved evidence. Corrective work must enter the normal change-management process.