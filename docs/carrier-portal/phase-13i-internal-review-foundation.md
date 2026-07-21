# WW.CX Carrier Portal Phase 13I — Internal Review Foundation

## Status

Implementation candidate. Repository validation is required before merge.

## Purpose

Phase 13I begins the internal carrier-support review console and lifecycle foundation for Phase 13H ticket and change-request intake records.

This phase deliberately does not add approval, scheduling, authorization, execution, or production-change capabilities.

## Internal scopes

The review foundation reserves two explicit internal scopes:

- `internal.carrier.review.read`
- `internal.carrier.review.write`

These are not carrier scopes and must never be assigned to carrier-originated identities.

## Review queue

`build_review_queue()` reads the append-only Phase 13H ticket and change-request JSONL files and overlays the latest internal review event for each resource.

Every queue response and item includes:

```json
{
  "execution_authorized": false
}
```

Unreviewed records receive `review_status: unreviewed`.

## Allowed lifecycle actions

Phase 13I permits only non-executing review actions:

- `acknowledge`
- `begin_review`
- `request_information`
- `close_ticket`
- `reject_change`

The implementation does not recognize actions named `approve`, `authorize`, `schedule`, or `execute`.

Ticket-only and change-only transitions are enforced:

- `close_ticket` applies only to tickets;
- `reject_change` applies only to change requests.

## Review evidence

Each accepted review event is appended as one JSON object per line and includes:

- generated `REV-` event ID;
- resource type and ID;
- action and resulting review status;
- internal reviewer client ID;
- optional note;
- UTC timestamp;
- `approval_granted: false`;
- `execution_authorized: false`.

Source ticket and change-request records are never rewritten by the review model.

## Security boundary

Phase 13I is an internal review and lifecycle-management foundation only.

It cannot:

- approve a carrier change request;
- schedule implementation;
- authorize execution;
- change SIP routing or numbering;
- modify credentials, firewall policy, or certificates;
- activate emergency calling;
- sign STIR/SHAKEN traffic;
- cut over production traffic.

Any future approval or execution plane must use separate identities, scopes, records, controls, and explicit authorization.

## Repository validation

```bash
python3 -m py_compile \
  server/portal/carrier_review.py \
  tests/portal/test_carrier_review.py

python3 -m unittest \
  tests.portal.test_carrier_review
```

The Phase 13G and Phase 13H portal tests should also remain green before API integration or deployment.

## Next implementation unit

After this model is validated, integrate internal-only authenticated endpoints for:

- read-only review queue retrieval;
- append-only lifecycle review events.

The API integration must reject carrier identities even if a scope is misconfigured and must not expose any approval or execution endpoint.
