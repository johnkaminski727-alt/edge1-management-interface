# WW.CX Carrier Portal Register

## Current Phase

Phase 13J — Internal Review Operations Readiness

Status: PLANNED

Phase 13J may prepare internal review operations, user-interface behavior, runbooks, and non-secret configuration validation. Creating or modifying a real reviewer credential remains a separate controlled authentication change.

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

### Phase 13I — Internal Carrier-Support Review Console

Status: COMPLETE

Completed and operationally verified:

- internal review queue model over Phase 13H append-only records;
- append-only internal review events;
- explicit `internal.carrier.review.read` and `internal.carrier.review.write` scopes;
- lifecycle states for acknowledgement, review, information requests, ticket closure, and change rejection;
- forced `approval_granted: false` and `execution_authorized: false`;
- explicit rejection of approve, authorize, schedule, and execute actions;
- `GET /portal/internal/carrier-review/queue`;
- `POST /portal/internal/carrier-review/events`;
- rejection of every identity carrying a `carrier_id`, even if an internal scope is misconfigured;
- append-only review-event and audit evidence;
- preservation of Phase 13G and Phase 13H routes;
- 27-test deployed validation suite;
- isolated authenticated HTTP validation;
- Edge1 deployment at merge commit `cb212ef8d35de42cbd70a09d0bedd6da2c2bacdb`;
- service health on `127.0.0.1:8097`;
- unauthenticated internal-queue denial;
- review log ownership `wwadmin:wwadmin` and mode `0640`;
- no production reviewer credential created or modified.

Implementation files:

```text
server/portal/carrier_review.py
server/portal/carrier_review_api.py
server/portal/portal_api_server.py
```

Documentation:

```text
docs/carrier-portal/phase-13i-internal-review-foundation.md
docs/carrier-portal/phase-13i-review-api-integration.md
docs/archive/WWCX-Carrier-Portal-Phase-13I-Operational-Completion-Archive.md
```

## Active Milestone

### Phase 13J — Internal Review Operations Readiness

Planned safe implementation units:

- internal review console presentation and queue filtering;
- operator-facing review-state summaries;
- non-secret reviewer configuration schema validation;
- audit-log inspection and evidence export tooling;
- deployment and rollback runbook refinement;
- negative authorization tests for carrier and insufficient-scope identities;
- explicit separation between reviewer actions and any future approval or execution plane.

Controlled follow-on requiring separate authorization:

- create or modify a real production reviewer identity or credential;
- grant `internal.carrier.review.read` or `internal.carrier.review.write` to a live identity;
- change production authentication policy or secret material.

## Security Boundaries

Carrier users remain isolated from:

- WW.CX admin users;
- store operations;
- PBX controls;
- Edge1 filesystem access;
- AI gateway credentials;
- direct routing or numbering mutation;
- automatic change approval or execution;
- internal carrier-support review scopes and records.

Phase 13I and Phase 13J review actions cannot grant approval or execution authority. Any future production approval or execution plane requires separate identities, scopes, records, controls, and explicit authorization outside standing routine authority.
