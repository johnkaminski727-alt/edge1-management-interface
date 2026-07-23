# WW.CX Carrier Portal Phase 13H — Service Workflows

## Status

Implementation candidate. Repository and non-production HTTP validation are required before deployment.

## Purpose

Phase 13H adds carrier-created support tickets and controlled change requests to the authenticated portal API.

The workflows are append-only intake records for internal review. They do not apply configuration, routing, numbering, credential, firewall, certificate, emergency-calling, STIR/SHAKEN, or traffic changes.

## Endpoints

| Method | Endpoint | Required scope | Result |
| --- | --- | --- | --- |
| `POST` | `/portal/carrier/tickets` | `carrier.ticket.create` | Creates an open carrier support ticket |
| `POST` | `/portal/carrier/change-requests` | `carrier.change.request` | Creates a requested change record with execution disabled |

These scopes are not included in the default Phase 13G read-only scope set. They must be assigned explicitly to an approved carrier client.

## POST authentication

Phase 13D GET signatures remain unchanged:

```text
HMAC-SHA256(secret, client_id + timestamp)
```

Phase 13H requests with a body require:

- `X-Portal-Client`
- `X-Portal-Timestamp`
- `X-Portal-Content-SHA256`
- `X-Portal-Signature`

The body digest is:

```text
SHA256(raw_request_body)
```

The POST signature is:

```text
HMAC-SHA256(secret, client_id + timestamp + body_digest)
```

This binds the exact submitted JSON bytes to the authenticated request. A missing or mismatched digest causes authentication failure.

## Ticket request

Example request body:

```json
{
  "category": "incident",
  "priority": "high",
  "summary": "Inbound call failures",
  "description": "Investigate repeated 503 responses observed during testing.",
  "reference": "INC-1001"
}
```

Allowed categories:

- `incident`
- `interconnect`
- `numbering`
- `billing`
- `general`

Created tickets receive:

- generated `TKT-` identifier;
- authenticated carrier and client ownership;
- `open` status;
- UTC creation and update timestamps.

## Change request

Example request body:

```json
{
  "category": "capacity_change",
  "priority": "normal",
  "summary": "Increase test capacity",
  "description": "Request review of a higher non-production channel limit.",
  "reference": "TEST-CHANGE-12"
}
```

Allowed categories:

- `sip_ip_update`
- `capacity_change`
- `routing_preference`
- `interconnect_modification`
- `testing_request`

Created change requests receive:

- generated `CRQ-` identifier;
- authenticated carrier and client ownership;
- `requested` status;
- `execution_authorized: false`;
- UTC creation and update timestamps.

No endpoint exists in Phase 13H to approve or execute a request.

## Validation limits

- Maximum request body: 16 KiB.
- Summary maximum: 160 characters.
- Description maximum: 4,000 characters.
- Priority must be `low`, `normal`, `high`, or `urgent`.
- Optional references accept only a bounded safe character set.
- JSON bodies must be objects.

## Storage

Default Edge1 paths:

```text
/var/lib/wwcx-portal/carrier_tickets.jsonl
/var/lib/wwcx-portal/carrier_change_requests.jsonl
```

Records are appended as one compact JSON object per line. Portal audit events remain in:

```text
/var/lib/wwcx-portal/portal_access_events.jsonl
```

Successful workflow audit events include the generated resource ID. Validation and authorization failures include a denial reason.

## Security boundary

- Carrier identity is mandatory.
- The exact workflow scope is mandatory.
- Write scopes are never granted by omission.
- Request bodies are included in the HMAC integrity boundary.
- The API records requests only.
- Change requests always set `execution_authorized` to false.
- Secrets and credentials remain outside source control.

## Repository validation

```bash
python3 -m py_compile \
  server/portal/carrier_workflows.py \
  server/portal/portal_api_server.py \
  tests/portal/test_carrier_workflows.py

python3 -m unittest \
  tests.portal.test_carrier_operational \
  tests.portal.test_carrier_workflows
```

## Deployment validation

Use an isolated server and temporary JSONL paths before restarting the live service. Verify:

1. valid ticket creation returns HTTP 201;
2. valid change request returns HTTP 201 and `execution_authorized: false`;
3. missing write scope returns HTTP 403;
4. missing carrier identity returns HTTP 403;
5. missing or invalid content digest returns HTTP 403;
6. tampered body returns HTTP 403;
7. invalid category returns HTTP 400;
8. legacy GET signatures and Phase 13G endpoints remain operational;
9. ticket, change, and audit JSONL records contain no secret material.

## Rollback

Restore the previous `portal_api_server.py`, remove `carrier_workflows.py`, and restart the service through the approved procedure. Existing JSONL intake records can be retained as audit evidence; no routing or production-state rollback is required.
