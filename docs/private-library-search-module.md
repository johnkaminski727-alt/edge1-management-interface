# Private Library Search Module

Date: 2026-07-16
Status: initial implementation brief

## Objective

Create a read-only, device-aware search module for the Edge1 private `operations` library.

The module should help an operator answer:

1. What do we know?
2. Where did the information come from?
3. What source document supports it?
4. Is the result safe to act on?

## MVP Scope

Included:

- Search input.
- Collection filter, initially restricted to `operations`.
- Result list.
- Result detail view.
- Source path, title, classification, locator, document ID, and chunk index.
- Desktop dense result layout.
- Mobile card result layout.
- Loading, empty, error, and result states.

Excluded from MVP:

- Import approval.
- Commit requests.
- Uploads.
- VPN changes.
- DNS changes.
- Firewall changes.
- Apply jobs.
- Rollback.
- Binary archive browsing.

## Access Boundary

- Private/VPN-only.
- Authenticated operator session.
- Read-only.
- No direct shell execution.
- No direct filesystem browsing.
- No broad backend tool exposure.

## Acceptance Criteria

- Search works against `operations`.
- Results show source title, source path, classification, locator, and excerpt.
- Phone layout renders cards without horizontal scrolling.
- Desktop layout supports dense scanning.
- No write actions are exposed.
- Backend errors do not leak internals.
- Retrieved text is visually treated as document data, not trusted UI copy.

