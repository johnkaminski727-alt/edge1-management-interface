# WW.CX Carrier Portal Register

## Current Phase

Phase 13H — Carrier Service Workflows

Status: IMPLEMENTATION IN PROGRESS

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

## Active Milestone

### Phase 13H — Carrier Service Workflows

Goals:

- carrier-created support tickets;
- controlled carrier change requests;
- explicit workflow write scopes;
- request-body integrity binding for authenticated POST requests;
- append-only workflow records;
- auditable generated ticket and change-request identifiers;
- no automatic production execution.

Planned endpoints:

- `POST /portal/carrier/tickets`
- `POST /portal/carrier/change-requests`

## Security Boundaries

Carrier users remain isolated from:

- WW.CX admin users;
- store operations;
- PBX controls;
- Edge1 filesystem access;
- AI gateway credentials;
- direct routing or numbering mutation;
- automatic change execution.

Phase 13H change requests are intake records only. Approval, scheduling, execution, and production verification remain internal, separately authorized workflows.

## Future Milestone

After Phase 13H validation and deployment, define the internal carrier-support review console and lifecycle transitions without allowing carrier-originated requests to bypass operational approval gates.
