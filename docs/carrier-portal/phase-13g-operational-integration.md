# WW.CX Carrier Portal Phase 13G — Operational Integration

## Status

Implementation candidate. Repository validation and deployment verification remain required before completion is declared.

## Purpose

Phase 13G connects the Phase 13F carrier identity plane to the Phase 13D authenticated Edge1 portal API. It adds carrier-scoped, read-only operational views without exposing credentials, private topology, or production mutation controls.

## Architecture

```text
Carrier portal user
        |
Carrier portal API client
        |
HMAC authenticated request
        |
Portal identity resolution
        |
Scope authorization
        |
Carrier tenant filter
        |
Sanitized exported Edge1 summary
```

The implementation consumes the existing JSON exports under:

```text
data/registry/interconnect/portal/
```

It does not directly query Asterisk, SIP proxies, production routing tables, carrier credentials, or private network configuration.

## Operational endpoints

| Endpoint | Required scope | Export |
| --- | --- | --- |
| `/portal/carrier/profile` | `carrier.profile.read` | `carrier-status.json` |
| `/portal/carrier/interconnects` | `carrier.interconnect.read` | `interconnect-status.json` |
| `/portal/carrier/numbers` | `carrier.numbering.read` | `numbering-status.json` |
| `/portal/carrier/metrics` | `carrier.metrics.read` | `health-summary.json` |
| `/portal/carrier/monitoring` | `carrier.monitoring.read` | `health-summary.json` |

The Phase 13D legacy endpoints remain available for existing authenticated clients.

## Client configuration

Each entry in `config/portal/client-credentials.json` may include:

```json
{
  "clients": {
    "example-carrier-client": {
      "secret": "managed-outside-source-control",
      "carrier_id": "example-carrier",
      "scopes": [
        "carrier.profile.read",
        "carrier.interconnect.read",
        "carrier.numbering.read",
        "carrier.metrics.read",
        "carrier.monitoring.read"
      ]
    }
  }
}
```

Rules:

- `secret` remains required when HMAC policy is enabled;
- `carrier_id` is required for carrier operational endpoints;
- omitted `scopes` default to the Phase 13G read-only scope set for backward-compatible configuration migration;
- explicit scopes are recommended for every carrier client;
- secrets must never be committed to the repository.

## Tenant filtering contract

Operational exports should identify ownership using one of:

- `carrier_id`
- `carrier`
- `carrier_slug`
- `tenant_id`

Supported export shapes are:

1. a top-level list of carrier-owned records;
2. a single carrier-owned object;
3. an object containing list-valued sections of carrier-owned records.

Records for other carriers are removed. Operational requests without a carrier identity are rejected.

## Sanitization

The response layer removes fields named:

- `secret`
- `password`
- `credential` or `credentials`
- `private_key`
- `api_key`
- `auth_token`
- `internal_ip`
- `management_ip`
- `network_topology`

Export producers should still avoid writing sensitive information into portal summaries. Sanitization is a defense-in-depth boundary, not permission to place secrets in exports.

## Audit events

Portal audit events now include, when available:

- client ID;
- carrier ID;
- endpoint;
- required scope;
- HTTP response code;
- denial or failure reason;
- correlation ID;
- UTC timestamp.

The default audit path remains:

```text
/var/lib/wwcx-portal/portal_access_events.jsonl
```

## Validation

Repository unit tests:

```bash
python3 -m unittest tests.portal.test_carrier_operational
```

Syntax validation:

```bash
python3 -m py_compile \
  server/portal/carrier_operational.py \
  server/portal/portal_api_server.py \
  tests/portal/test_carrier_operational.py
```

Recommended non-production smoke validation:

1. configure a test client with a non-production carrier ID and explicit read scopes;
2. create fixture exports containing records for two carrier IDs;
3. sign requests using the existing Phase 13D HMAC process;
4. verify each carrier endpoint returns only the configured carrier records;
5. verify sensitive fields are absent;
6. verify missing carrier identity and missing scope both return HTTP 403;
7. inspect the JSONL audit event for carrier ID, required scope, response code, and correlation ID.

## Deployment boundary

Repository completion does not authorize deployment or modification of live credentials. Deployment requires an Edge1 operator to:

- pull the reviewed commit;
- run syntax and unit validation;
- update client configuration without exposing secrets;
- restart the portal API service under the normal change procedure;
- run authenticated, non-production smoke requests;
- confirm the audit log and legacy endpoints remain operational.

## Rollback

Revert the Phase 13G commit or restore the prior `portal_api_server.py`, then restart the portal API service. No data migration or production routing rollback is required because Phase 13G is read-only and uses existing exported summaries.