# WW.CX Carrier Portal Phase 13H — Operational Completion Archive

Status: COMPLETE

Date: 2026-07-21

## Scope

Phase 13H adds carrier-originated support tickets and controlled change-request intake to the authenticated Edge1 portal API.

The workflows are append-only intake records for internal review. They do not approve, schedule, or execute routing, numbering, credential, firewall, certificate, emergency-calling, STIR/SHAKEN, or traffic changes.

## Repository evidence

- Pull request: #47, `Add Phase 13H carrier service workflows`
- Merge commit: `fdf0ad87224bc05867ccbae325fdd517b62c2dba`
- Changed files:
  - `server/portal/carrier_workflows.py`
  - `server/portal/portal_api_server.py`
  - `tests/portal/test_carrier_workflows.py`
  - `docs/carrier-portal/phase-13h-service-workflows.md`
  - `docs/project-register/wwcx-carrier-portal-register.md`

## Verified repository validation

Executed on Edge1 under `/opt/edge1-management-interface`:

- Python compilation passed for the Phase 13G and Phase 13H portal modules and tests.
- Fourteen targeted tests ran.
- Fourteen targeted tests passed.
- No failures or errors were reported.

## Verified isolated authenticated HTTP validation

An isolated server on `127.0.0.1:18098` used temporary credentials, exports, workflow records, and audit files.

Verified results:

- valid ticket creation returned HTTP 201;
- valid change-request creation returned HTTP 201;
- submitted `execution_authorized: true` was stored as `false`;
- a client missing the ticket scope received HTTP 403 with `scope denied`;
- a client missing carrier identity received HTTP 403 with `carrier identity is required`;
- missing and incorrect body digests failed authentication with HTTP 403;
- an invalid category returned HTTP 400;
- ticket, change-request, and audit records were written to isolated append-only JSONL files;
- no smoke-test secret appeared in stored records.

## Verified Edge1 deployment

The Edge1 worktree was updated to merged `main` at commit `fdf0ad87224bc05867ccbae325fdd517b62c2dba`.

The portal API service was restarted successfully:

- service: `wwcx-portal-api.service`
- previous PID: `432269`
- new PID: `435663`
- state after restart: `active (running)`
- listener: `127.0.0.1:8097`
- executable: `/usr/bin/python3 /opt/edge1-management-interface/server/portal/portal_api_server.py`

The storage directory `/var/lib/wwcx-portal` was confirmed with owner and group `wwadmin` and mode `0750` through the deployment procedure.

The existing live portal client retained no carrier workflow authority. The live ticket endpoint returned HTTP 403 as expected, confirming the deployed code remains gated until an approved client receives an explicit workflow scope and carrier identity.

## Security and operational boundary

Phase 13H does not grant any production carrier client a workflow scope. It does not apply carrier-submitted changes, change routing or numbering, expose credentials, alter firewall or certificate state, activate emergency calling, sign STIR/SHAKEN traffic, or cut over production traffic.

Change requests remain intake records only and always set `execution_authorized` to `false`.

## Completion conclusion

Phase 13H repository implementation, unit validation, authenticated HTTP validation, Edge1 deployment, storage preparation, service restart, and live authorization-gate verification are complete.

The next milestone is an internal carrier-support review console and controlled lifecycle transitions. That future work must preserve the separation between carrier-originated requests and internal approval or execution authority.
