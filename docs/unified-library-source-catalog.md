# Unified Private Library Source Catalog

## Purpose

The Edge1 Private Library is the unified searchable catalog for operational, business, accounting, contact, legal, and evidentiary records. External providers remain authoritative for their own storage, while Edge1 records stable source identity, searchable projections, processing state, and preserved evidence where policy requires it.

## Architecture

1. **Source Registry** — approved Google Drive roots, Dropbox roots, Airtable bases/tables, ChatGPT Library, Mail Room, local folders, and future providers.
2. **Source Catalog** — one normalized record for every known external item, provider ID, parent, revision, timestamps, URL/path, MIME type, size, hash, copy state, and processing state.
3. **Private Library Index** — searchable text/chunks/embeddings. It is an index, not the sole evidence store.
4. **Evidence Register** — content-addressed immutable local copies with SHA-256 and manifests where evidence preservation is required.
5. **Domain Processors** — Contacts, Filing, Accounting, and future processors consume the same catalog item and record their independent processing state.
6. **Review/Automation** — deterministic verified facts may be applied automatically; conflicts, destructive changes, restricted material, and weak extraction remain review-gated.

## Copy policies

- `reference`: retain provider identity/metadata and searchable projection; source bytes stay with provider.
- `cache`: retain a replaceable local working copy for indexing/reprocessing.
- `evidence`: preserve original bytes content-addressably, hash them, create a manifest, and link an Evidence Register source document.

Remote deletion never automatically deletes a preserved evidence object. Instead, the catalog marks the upstream item `deleted_remote` while retaining local evidence and audit history.

## Source policy

Each source has provider, locator, runtime access, classification, sensitivity, enabled state, copy policy, allowed domains, and rules. Multiple roots from the same provider are first-class independent sources.

Credential stores, recovery codes, secret-key material, and similar authentication artifacts are explicitly excluded from ordinary Library indexing. Restricted personal/infrastructure sources may be catalogued as references without making their contents broadly searchable.

## Item identity and lifecycle

Every catalog item receives a stable Edge1 item ID derived from provider and external identity. Provider file/record IDs are retained. Modified/revision values drive delta sync. SHA-256 identifies preserved content independently of file name or folder location.

Item copy states: `reference`, `cached`, `preserved`, `missing`, `unavailable`.

Sync states: `current`, `new`, `changed`, `deleted_remote`, `deferred`, `error`.

## Domain processing

Each item independently tracks processing state for:

- `filing` — classification, naming, indexing, retention placement.
- `contacts` — organizations/people/contact coordinates/relationships with provenance.
- `accounting` — statements, invoices, receipts, bills, transactions, reconciliation.

Adding another domain must not require duplicating the source document.

## Accounting model

Accounting document facts include vendor, document kind, issue date, statement/service period, account reference, invoice number, currency, subtotal, tax, total amount, balance due, due date, payment status, duplicate key, extraction confidence, review status, and source hash.

Line items retain description, quantity, unit amount, line amount, tax code, service period, and metadata. Reconciliation links associate a source item with an external accounting/banking record without mutating that external system.

The accounting subsystem may classify and stage automatically. Payment initiation, bank mutation, tax filing, destructive reconciliation, or irreversible accounting changes require separate authorization.

## Current approved external roots

The source registry currently includes the SaskTel Google Drive evidence archive; Dropbox Documents and Filing; Dropbox Personal Documents (restricted); Dropbox Trademark Filing - CIPO; Dropbox Edge1 Recovery (restricted); operational Airtable People and Organizations; and ChatGPT Library.

Dropbox Keys and 2FA Recovery Codes are explicitly excluded from indexing.

## Synchronization contract

A provider adapter should:

1. enumerate only its approved source root;
2. retain provider IDs, parent IDs, modification/revision timestamps, path/URL and metadata;
3. compare against catalog state and process deltas only;
4. download bytes only when copy policy requires it;
5. verify hashes before evidence registration;
6. update the Private Library projection;
7. invoke applicable domain processors;
8. record a sync-run result and errors without silently dropping items;
9. never delete or alter the upstream provider unless a separate explicit action is authorized.

Connector-required sources remain `deferred` until a server-side bridge is available. Deferred is a normal source state, not a failed sync.
