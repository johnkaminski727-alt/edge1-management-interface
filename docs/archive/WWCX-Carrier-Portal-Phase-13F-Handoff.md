# WW.CX Carrier Portal — Phase 13F Archive Handoff

Status:
COMPLETE

Milestone:
Carrier Identity, Registry, Import, and Onboarding Foundation

## Completed

- Separate carrier identity plane
- Separate carrier authentication
- Separate carrier session namespace
- Carrier SQLite database
- Carrier registry
- Carrier user management foundation
- Carrier invitations
- Carrier activation workflow
- CSV carrier import staging
- Import approval workflow
- Duplicate protection
- Admin carrier management foundation

## Architecture

WW.CX Platform

Internal Admin:

/admin/

Uses:
- WW.CX internal users
- Store/admin authentication


Carrier Portal:

/carrier-portal/

Uses:
- carrier_users
- carrier authentication
- carrier session


Edge1 Integration:

portal.ww.cx

Uses:
- HMAC authenticated portal API

## Carrier Database

Location:

/home/wwcxjywl/carrier-private/carrier.sqlite

Tables:

- carriers
- carrier_users
- carrier_invitations
- carrier_audit_log
- carrier_imports
- carrier_import_rows

## Completed Validation

Confirmed:

- carrier registry creation
- CSV import
- import approval
- invitation creation
- activation flow
- carrier user creation
- carrier portal authentication

## Next Phase

Phase 13G:

- carrier scoped dashboard
- Edge1 API filtering
- carrier operational views
- interconnect monitoring
- numbering visibility

