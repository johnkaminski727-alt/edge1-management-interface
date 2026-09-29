# Edge1 Unified Contacts — Phase 3F Release

Date: 2026-09-28

## Status

Phase 3F establishes the first production Unified Contacts read surface on
Edge1.

Phone Intelligence is expanded into a carrier-neutral contacts model while
identity, evidence/provenance, and contextual observations remain separate.

## Architectural rule

Unified Contacts maintains three distinct layers:

1. Canonical Contacts — identity facts belonging to a person,
   organization, or contact endpoint.
2. Evidence and Provenance — source and verification information
   explaining why an assertion or observation exists.
3. Connections and Observations — contextual relationships,
   co-occurrences, and candidate associations that are not automatically
   identity facts.

Document co-occurrence does not establish ownership or identity.
Normalization does not imply identity merging.
Uncertain matches remain separate until reviewed.

## Production state

- contact entities: 50
- organizations: 50
- people: 0
- contact points: 677
- phone contact points: 677
- email contact points: 0
- assertions: 50
- confirmed assertions: 48
- probable assertions: 2
- unassigned contact points: 627
- provenance records: 727
- assertion-evidence links: 50
- observations: 1,566
- candidate correlations: 0
- rejected extractions: 0

## Evidence provenance

The 677 legacy evidence records are retained as provenance.

- 48 verified evidence records support confirmed assertions.
- 2 probable associations remain unverified.
- 627 unresolved numbers remain unverified and create no identity
  assertion.

No source-document relationship was inferred where the legacy evidence did
not explicitly establish one.

Entity verification was reconciled from evidence:

- 48 verified entities
- 2 unverified entities

## Document observations

The legacy occurrence table contains 1,566 unique phone-to-document
relationships.

These are workbook-level source relationships, not individual telephone
calls.

The legacy aggregate occurrence total of 4,255 remains aggregate legacy
information and was not expanded into synthetic observations.

The bridge created:

- 50 document provenance records
- 1,566 observations
- 5 document-sourced/recovered records
- 45 missing-source records
- 169 observations associated with recovered-document provenance
- 1,397 observations associated with missing-source provenance

All migrated observations retain:

- confidence: unverified
- classification: unknown
- occurred_at: NULL
- direction: NULL

No timestamp, direction, ownership, or identity relationship was inferred.

Release hardening verified 1,566 unique semicolon-terminated
`legacy_occurrence_id=N;` markers corresponding exactly to the legacy
occurrence IDs.

## Source limitation

Only 5 of the 50 legacy source documents are currently recovered.

The remaining 45 are deliberately represented as `missing_source`.

This release does not claim that all 50 source documents were independently
reverified.

## Read API

The authenticated Operations API on 127.0.0.1:8097 provides:

- `/v1/contacts/summary`
- `/v1/contacts/search`
- `/v1/contacts/unassigned`
- `/v1/contacts/sources`
- `/v1/contacts/observations`
- `/v1/contacts/evidence`

The private web gateway on 127.0.0.1:8098 exposes corresponding explicitly
allowlisted browser routes under `/api/contacts/`.

The browser does not receive the Operations API HMAC credential.

Malformed numeric query parameters return controlled HTTP 400 responses
with stable field-oriented messages.

## Web interface

The release adds Unified Contacts, Sources, Observations, separate identity
evidence and contextual observations, carrier-neutral terminology, and
generated shared Intelligence navigation.

Phone Directory remains a projection of the broader Contacts model.

Read surfaces currently use bounded result sizes. Pagination and broader UX
refinement remain future work.

## Private network boundary

- 8097 — Operations API — loopback only
- 8098 — private web gateway — loopback only
- 8102 — MCP transport — loopback only
- 18098 — historical WW.CX Portal API Bridge reservation — dormant and
  loopback-only when explicitly run

No 18098 listener is required by Unified Contacts.

The Portal API implementation remains because carrier workflow and Control
Centre components still reference it.

Port 8098 must not be exposed publicly.

SSH forwarding remains an administrative/development fallback until the
Edge1 Private Access Gateway provides stable private addresses, human
authentication, and application authorization.

## Release validation

Phase 3F validates:

- SQLite integrity
- zero foreign-key errors
- exact production counts
- migration idempotency
- duplicate provenance detection
- duplicate observation-marker detection
- exact observation-marker coverage
- controlled malformed-request HTTP 400 handling
- positive live API contracts
- loopback confinement
- Contacts and Phone Directory delivery
- generated Intelligence navigation
- repository whitespace quality
