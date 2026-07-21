# WW.CX Carrier Portal Phase 13G — Operational Completion Archive

Status: COMPLETE

Date: 2026-07-21

## Scope

Phase 13G connects the Phase 13F carrier identity plane to the Phase 13D authenticated portal API through carrier-scoped, read-only operational views.

## Completed implementation

- carrier identity resolution from the existing portal client configuration;
- explicit read-scope authorization;
- carrier tenant filtering for exported operational summaries;
- sensitive-field sanitization;
- carrier-scoped profile, interconnect, numbering, metrics, and monitoring endpoints;
- expanded portal access audit records;
- preservation of existing Phase 13D legacy endpoints;
- focused unit coverage and operator documentation.

## Repository evidence

- Pull request: #43, `Add Phase 13G carrier operational portal integration`
- Implementation merge commit: `698db20cd64db3a72e5a24bc0f80744a35d87d86`
- Repository archive pull request: #45
- Repository archive merge commit: `0ea7f5f9d5af6ee184b52a836a832fb997de07c2`
- Changed files:
  - `server/portal/carrier_operational.py`
  - `server/portal/portal_api_server.py`
  - `tests/portal/test_carrier_operational.py`
  - `docs/carrier-portal/phase-13g-operational-integration.md`

## Verified repository validation

Executed on Edge1 under `/opt/edge1-management-interface`:

```bash
python3 -m py_compile \
  server/portal/carrier_operational.py \
  server/portal/portal_api_server.py \
  tests/portal/test_carrier_operational.py

python3 -m unittest tests.portal.test_carrier_operational
```

Result:

- Python compilation passed.
- Seven targeted tests ran.
- Seven targeted tests passed.
- No failures or errors were reported.

## Verified Edge1 deployment

The Edge1 worktree was updated to merged `main` at commit `0ea7f5f9d5af6ee184b52a836a832fb997de07c2`.

The portal API service was restarted through systemd:

- service: `wwcx-portal-api.service`
- previous PID: `376311`
- new PID: `432269`
- state after restart: `active (running)`
- listener: `127.0.0.1:8097`
- executable: `/usr/bin/python3 /opt/edge1-management-interface/server/portal/portal_api_server.py`

Legacy authenticated endpoints were verified after restart:

- `/portal/status`: HTTP 200
- `/portal/health`: HTTP 200
- `/portal/carriers`: HTTP 200

The existing shared-hosting portal client has no carrier identity configured. All five carrier endpoints correctly returned HTTP 403 with `carrier identity is required`, confirming the live tenant-identity gate.

## Verified isolated authenticated smoke test

A temporary isolated server was started on `127.0.0.1:18097` using fixture credentials and carrier-owned exports. No live client credential or production routing configuration was changed.

Successful carrier-scoped requests:

- `/portal/carrier/profile`: HTTP 200
- `/portal/carrier/interconnects`: HTTP 200
- `/portal/carrier/numbers`: HTTP 200
- `/portal/carrier/metrics`: HTTP 200
- `/portal/carrier/monitoring`: HTTP 200

Authorization failures behaved as designed:

- client missing required interconnect scope: HTTP 403, `scope denied`
- client missing carrier identity: HTTP 403, `carrier identity is required`

Isolation and sanitization were verified:

- no records belonging to the second carrier were returned;
- secret, password, and internal IP fixture values were removed;
- no sensitive or cross-carrier fixture value appeared in the validated responses.

Audit validation passed for seven events. Events included:

- client ID;
- carrier ID where available;
- endpoint;
- required scope;
- HTTP response code;
- denial reason where applicable;
- correlation ID;
- UTC timestamp.

## Security and operational boundary

Phase 13G is read-only. It does not change live SIP routing, numbering assignments, firewall policy, certificates, emergency calling, STIR/SHAKEN signing, or carrier traffic.

No production carrier client identity was created as part of validation. Future carrier activation requires an approved client-to-carrier mapping and explicit scopes managed outside source control.

## Completion conclusion

Phase 13G repository implementation, Edge1 service deployment, backward-compatibility verification, carrier authorization, tenant isolation, sensitive-field sanitization, and audit behavior are complete and verified.

Future work begins with the next carrier-portal phase or controlled onboarding of an approved non-production carrier client. Neither action is included in this completion record.
