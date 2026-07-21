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