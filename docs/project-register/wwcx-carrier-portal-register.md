# WW.CX Carrier Portal Register

## Current Phase

Phase 13H — Carrier Service Workflows

Status: COMPLETE

## Completed Milestones

### Phase 13F — Carrier Identity and Onboarding Foundation

Completed:

- external carrier identity;
- separate carrier authentication and sessions;
- carrier registry;
- carrier onboarding and CSV import workflow;
- carrier invitations and activation;
- carrier user foundation.

### Phase 13G — Carrier Operational Portal Integration

Status: COMPLETE

Completed and operationally verified:

- carrier-scoped profile, interconnect, numbering, metrics, and monitoring views;
- HMAC-authenticated Edge1 API integration;
- explicit read scopes;
- tenant isolation;
- sensitive-field sanitization;
- expanded audit events;
- legacy endpoint compatibility;
- Edge1 service deployment and authenticated smoke validation.

Operational completion archive:

```text
docs/archive/WWCX-Carrier-Portal-Phase-13G-Repository-Completion-Archive.md
```

### Phase 13H — Carrier Service Workflows

Status: COMPLETE

Completed and operationally verified:

- carrier-created support tickets;
- controlled carrier change-request intake;
- explicit `carrier.ticket.create` and `carrier.change.request` scopes;
- request-body SHA-256 integrity binding for authenticated POST requests;
- append-only ticket and change-request JSONL records;
- auditable generated ticket and change-request identifiers;
- forced `execution_authorized: false` for every change request;
- isolated authenticated HTTP validation;
- Edge1 service deployment and live authorization-gate validation.

Operational completion archive:

```text
docs/archive/WWCX-Carrier-Portal-Phase-13H-Operational-Completion-Archive.md
```

## Security Boundaries

Carrier users remain isolated from:

- WW.CX admin users;
- store operations;
- PBX controls;
- Edge1 filesystem access;
- AI gateway credentials;
- direct routing or numbering mutation;
- automatic change approval or execution.

Carrier workflow scopes are explicit and are not part of the default read-only scope set. No production carrier client received a workflow scope during Phase 13H validation or deployment.

## Next Milestone

### Phase 13I — Internal Carrier-Support Review Console

Goals:

- internal read-only review of carrier tickets and change requests;
- controlled lifecycle transitions with append-only audit evidence;
- separation of review, approval, scheduling, execution, and verification roles;
- no carrier-originated approval or execution authority;
- no automatic routing, numbering, credential, firewall, certificate, emergency-calling, STIR/SHAKEN, or traffic changes.

Phase 13I must begin as an internal review and lifecycle-management foundation. Any endpoint or workflow that can authorize or execute a production change remains separately gated and outside standing routine authority.
