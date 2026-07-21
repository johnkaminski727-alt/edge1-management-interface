# WW.CX Carrier Portal Phase 13I — Internal Review API Integration

## Status

Implementation candidate. Edge1 repository and isolated authenticated HTTP validation are required before merge and deployment.

## Endpoints

| Method | Endpoint | Scope | Purpose |
| --- | --- | --- | --- |
| `GET` | `/portal/internal/carrier-review/queue` | `internal.carrier.review.read` | Read the internal review queue |
| `POST` | `/portal/internal/carrier-review/events` | `internal.carrier.review.write` | Append a non-executing lifecycle review event |

## Identity boundary

Internal review endpoints require an authenticated portal client with no `carrier_id` and the exact internal scope.

A client carrying a `carrier_id` is rejected even if an internal scope is accidentally configured. Internal review scopes must never be granted to carrier-originated identities.

## Queue behavior

The queue combines the Phase 13H append-only ticket and change-request records with the latest internal review event for each resource.

Responses always include:

```json
{
  "execution_authorized": false
}
```

Each queue item also forces `execution_authorized: false` and exposes review state only. Source intake records are not rewritten.

## Lifecycle event behavior

Accepted POST actions remain limited to:

- `acknowledge`
- `begin_review`
- `request_information`
- `close_ticket`
- `reject_change`

The API does not expose approval, authorization, scheduling, or execution actions. Every accepted event forces:

```json
{
  "approval_granted": false,
  "execution_authorized": false
}
```

POST bodies remain protected by the Phase 13H SHA-256 body digest and HMAC signature binding.

## Audit behavior

Successful queue reads and review events are written to the portal audit JSONL log. Lifecycle writes include the generated `REV-` resource identifier. Authentication, carrier-identity, scope, and validation failures record explicit denial reasons.

## Storage

Default Edge1 paths:

```text
/var/lib/wwcx-portal/carrier_tickets.jsonl
/var/lib/wwcx-portal/carrier_change_requests.jsonl
/var/lib/wwcx-portal/carrier_review_events.jsonl
/var/lib/wwcx-portal/portal_access_events.jsonl
```

The review API appends lifecycle records and never rewrites carrier intake records.

## Security boundary

The implementation cannot:

- approve a carrier request;
- authorize or schedule implementation;
- execute routing or numbering changes;
- modify credentials, firewall policy, or certificates;
- activate emergency calling;
- sign STIR/SHAKEN traffic;
- cut over production traffic.

Any future approval or execution plane requires separate identities, scopes, records, controls, and explicit authorization.

## Repository validation

```bash
python3 -m py_compile \
  server/portal/carrier_review.py \
  server/portal/carrier_review_api.py \
  server/portal/portal_api_server.py \
  tests/portal/test_carrier_review.py \
  tests/portal/test_carrier_review_api.py

python3 -m unittest \
  tests.portal.test_carrier_review \
  tests.portal.test_carrier_review_api \
  tests.portal.test_carrier_operational \
  tests.portal.test_carrier_workflows
```

## Isolated HTTP validation

Before merge and deployment, verify with temporary credentials and JSONL files:

1. internal queue read returns HTTP 200;
2. internal lifecycle event creation returns HTTP 201;
3. carrier identity with internal scope returns HTTP 403;
4. missing internal scope returns HTTP 403;
5. approval, authorization, scheduling, and execution actions return HTTP 400;
6. append-only review and audit records contain no secrets;
7. Phase 13G and Phase 13H routes remain operational.

## Rollback

Revert the Phase 13I API integration commits and restore the previous portal API server. Existing review JSONL evidence can remain archived; no production routing or customer-traffic rollback is required.
