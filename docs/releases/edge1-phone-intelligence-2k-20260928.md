# Edge1 Phone Intelligence / Phone Directory Release

Release: edge1-phone-intelligence-2k-20260928
Date: 2026-09-28
Repository baseline: 723e712775da5534042a146a725fa63a9da39421

## Scope

Private, authenticated, read-only Edge1 Phone Intelligence service
and Phone Directory interface.

This release introduces:

- SQLite-backed phone intelligence read model.
- Authenticated Operations API intelligence routes.
- Dedicated loopback-only private web gateway.
- Carrier-neutral Phone Directory interface.
- Purpose-built responsive/mobile presentation.
- Search, status filtering, source relationships and evidence detail.
- Read-only browser architecture with no backend HMAC secret exposed.
- Explicit source-document provenance.
- Deterministic SQLite connection closure.
- Preserved Operations API transaction semantics.

## Dataset acceptance

- Phone numbers: 677
- Confirmed: 48
- Probable: 2
- Unresolved: 627
- Aggregate call occurrences: 4,255
- Source relationships: 1,566
- Source documents referenced: 50
- Source PDFs independently recovered: 5
- Referenced source PDFs not independently recovered: 45

A source-document status of "missing" means the document is referenced
by the imported research dataset but its underlying PDF was not
independently recovered during the reconstruction audit. It does not
mean the associated phone number or contact record is missing.

## Security

- Operations API: 127.0.0.1:8097
- Private web gateway: 127.0.0.1:8098
- Browser receives no Operations API HMAC secret.
- Mutating intelligence requests are rejected.
- Existing Operations API mutation gates remain disabled.
- No public listener was introduced.

## Validation

- 28/28 automated tests passing.
- Zero unclosed SQLite ResourceWarnings.
- SQLite integrity_check: ok.
- Foreign-key errors: 0.
- Post-restart API/dashboard acceptance passed.
- Static source and deployed UI hashes matched.

## Mobile acceptance

Responsive/mobile implementation is included.

Physical mobile-device acceptance is intentionally deferred until the
separate Edge1 Private Access Gateway provides the approved private
mobile authentication/access path.

## Rollback

Release backup:

/var/backups/edge1-phone-intelligence-2k-20260928-20260928T220522Z

Rollback requires restoring the backed-up application files and, only
if database provenance must also be reverted, the backed-up SQLite
database. Services must then be restarted and the health/security
acceptance checks repeated.

Do not expose ports 8097 or 8098 publicly as part of rollback or
recovery.
