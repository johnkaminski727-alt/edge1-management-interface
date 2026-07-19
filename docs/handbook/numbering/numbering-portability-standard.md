# Numbering and Portability Standard

## Purpose

Define how WW.CX prepares for, receives, inventories, assigns, ports, routes, audits, and retires telephone-number resources without claiming authority or assignments that have not been granted.

## Authority boundary

No document, database, user interface, or test fixture may represent an OCN, SPID, LRN, NPA-NXX, thousand-block, CLEC status, registration, or regulatory approval as active unless supported by authoritative evidence. Proposed identifiers MUST be labelled pending or placeholder.

## Source of truth

Maintain a controlled numbering register containing:

- number or range;
- country, NPA, rate centre, and jurisdiction;
- resource provider and underlying carrier;
- assignment authority and evidence reference;
- service state and customer/service association;
- routing destination and portability status;
- emergency-service address or applicability reference;
- activation, aging, quarantine, and retirement dates;
- accountable owner and last reconciliation date.

The register MUST distinguish owned or directly assigned resources from hosted, leased, ported-in, test, reserved, and synthetic resources.

## Lifecycle

Use these minimum states: requested, reserved, available, assigned, activating, active, suspended, port-pending, aging, quarantined, disconnected, and returned. Transitions MUST be authorized, timestamped, attributable, and reversible where possible.

## Assignment controls

- Validate number format, jurisdiction, service eligibility, routing, and inventory state before assignment.
- Prevent duplicate assignment through transactional controls.
- Do not activate a number until voice, messaging, emergency-service, privacy, billing, and customer-record dependencies are satisfied where applicable.
- Recycled numbers MUST complete the approved aging and quarantine period before reassignment.
- Bulk changes MUST support preview, validation, bounded execution, evidence, and rollback.

## Portability

Port workflows MUST preserve order identifiers, customer authorization evidence, losing and gaining provider references, firm order commitment information, due dates, validation responses, exceptions, and completion evidence. Operational systems MUST not infer completion solely from a submitted request.

Before a port cutover, confirm:

- authorization and data accuracy;
- route and endpoint readiness;
- emergency-service implications;
- messaging implications;
- directory or caller-name implications where applicable;
- monitoring and customer communication;
- fallback or escalation plan.

After cutover, validate inbound and outbound calling, identity presentation, messaging where supported, emergency-routing posture where applicable, and authoritative routing/portability records.

## Data quality and reconciliation

Reconcile inventory regularly against provider portals, invoices, portability records, routing configuration, customer assignments, and authoritative datasets. Exceptions MUST be recorded and assigned. Automated imports MUST record source, retrieval time, checksum, accepted and rejected row counts, parser version, and replacement behavior.

## Forecasting and utilization

Forecasts submitted for numbering-resource planning MUST be reproducible and distinguish actual utilization, committed demand, forecast demand, reserved capacity, aging inventory, and unavailable resources. Never invent customers or demand to justify an application.

## Security and privacy

Restrict access to customer-number associations, porting authorization, account identifiers, and emergency-service addresses. Logs and evidence exports SHOULD minimize personal information while preserving operational traceability.

## Incident handling

Treat unauthorized ports, route hijacks, duplicate assignments, emergency-address mismatches, and unexplained inventory discrepancies as high-severity events. Preserve records, limit further changes, reconcile authoritative sources, and escalate through the incident and regulatory procedures applicable to the event.

## Retirement

Retirement MUST remove service dependencies, preserve required records, apply aging or quarantine policy, reconcile billing and provider inventory, and document whether the number was returned, retained, or transferred.