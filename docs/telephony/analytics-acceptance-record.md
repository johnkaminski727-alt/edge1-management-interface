# Telephony Analytics Acceptance Record

## Scope

This record documents repository validation of the Edge1 Telephony Analytics implementation and defines the separate live-acceptance boundary.

The analytics layer is intentionally read-only and provides normalized operational visibility only.

It does not authorize:

- carrier routing changes;
- PBX configuration changes;
- call origination or DTMF transmission;
- number assignment changes;
- production traffic activation;
- emergency-calling changes;
- database or credential access;
- public listener exposure.

## Repository validation

Repository:

- `johnkaminski727-alt/edge1-management-interface`
- authoritative branch: `main`

Validation commands:

- `python3 tests/validate_telephony_console.py`
- `python3 tests/validate_telephony_platform.py`
- `python3 tests/validate_telephony_analytics_api.py`
- `python3 tests/validate_telephony_analytics_live_acceptance_audit.py`

Repository result:

- aggregate health, call, and interconnect analytics are implemented;
- the API exposes read-only GET endpoints;
- write-method handling is bounded;
- the systemd unit is configured for loopback-only port `8099` with hardening controls;
- the live acceptance audit contains no install, enable, start, stop, restart, reload, call, route, database, carrier, firewall, certificate, DNS, or configuration mutation path.

## Runtime surfaces

The telephony console and analytics API are separate loopback services:

- console/status surface: `http://127.0.0.1:8096`;
- aggregate analytics API: `http://127.0.0.1:8099`.

Analytics endpoints:

- `/healthz`;
- `/api/telephony/platform/health`;
- `/api/telephony/platform/calls/summary`;
- `/api/telephony/platform/interconnects/summary`.

## Live acceptance

Repository completion does not by itself prove that the analytics unit is installed, active, hardened as expected, or bound only to loopback on Edge1.

Live acceptance requires an authenticated run of:

```text
tools/telephony/telephony_analytics_live_acceptance_audit.sh
```

Runbook:

```text
docs/telephony/telephony-analytics-live-acceptance.md
```

The audit must capture protected evidence under:

```text
/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/<UTC timestamp>
```

An accepted run must confirm:

- clean authoritative repository state;
- active service under `wwadmin`;
- expected loopback-only command and listener on `127.0.0.1:8099`;
- successful JSON responses from all aggregate endpoints;
- HTTP `405` for POST;
- aggregate payload contract and privacy scan;
- no service or runtime mutation;
- zero failures.

## Operational status

Repository implementation: **complete**.

Authenticated Edge1 live acceptance: **pending operator execution and review**.

Remaining future work requires separate authorization or a new bounded repository increment:

- sanitized CDR and SIP-event adapters;
- dashboard panels for health score, failure classes, and carrier performance;
- append-only analytics report audit events;
- live carrier integrations;
- production collectors requiring credential or database access;
- routing automation or write-plane capabilities;
- external exposure.
