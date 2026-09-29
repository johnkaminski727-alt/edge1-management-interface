# Unified Contacts Phase 3F Release Register

Date: 2026-09-28

## Decision

Release the first production Unified Contacts read surface while preserving
strict separation between canonical identity, evidence/provenance, and
contextual observations/connections.

## Production counts

- entities: 50
- organizations: 50
- people: 0
- contact points: 677
- assertions: 50
- confirmed: 48
- probable: 2
- unassigned: 627
- provenance: 727
- assertion-evidence links: 50
- observations: 1,566
- candidate correlations: 0
- rejected extractions: 0

## Provenance

Legacy evidence:

- 677 total
- 48 verified
- 629 unverified
- the 629 comprise 2 probable associations and 627 unresolved numbers

Document provenance:

- 50 total
- 5 document-sourced/recovered
- 45 missing-source

Only five source documents are currently recovered. No claim is made that
all 50 documents were independently reverified.

## Observation semantics

The 1,566 observations are unique workbook-level phone-to-source-document
relationships, not individual calls.

The legacy aggregate occurrence total of 4,255 was not converted into
synthetic observations.

Document co-occurrence does not establish phone ownership or identity.

## Network boundary

- Operations API: 127.0.0.1:8097
- private web gateway: 127.0.0.1:8098
- MCP transport: 127.0.0.1:8102
- historical Portal API: 127.0.0.1:18098 only when explicitly run

The Portal API is dormant at this checkpoint. Its implementation remains
because carrier and Control Centre components reference it.

No public exposure of these internal application ports is authorized by
this release.

## Acceptance gates

- database integrity PASS
- foreign-key check PASS
- production counts exact
- bridge idempotency PASS
- observation-marker integrity PASS
- duplicate detection PASS
- malformed API contracts HTTP 400 PASS
- positive live API contract PASS
- loopback confinement PASS
- static UI PASS
- generated navigation PASS
- repository quality PASS
