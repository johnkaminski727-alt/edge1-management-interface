# WW.CX Operational Records Evidence Program

## Purpose

This program turns records-management policy into reproducible evidence. It applies to public engineering records in this repository and provides a safe model for controlled internal records.

## Required evidence

Each governed record set should include:

1. A stable WWCX record identifier.
2. A machine-readable metadata record validated against `schemas/records-evidence.schema.json`.
3. A SHA-256 manifest covering preserved objects.
4. Provenance identifying the authoritative source and responsible custodian.
5. A retention assignment and sensitivity classification.
6. Preservation events for creation, validation, migration, fixity checks, restoration tests, and disposition.
7. Restoration instructions and periodic restore-test evidence for archival packages.

## Lifecycle

`capture -> classify -> validate -> package -> preserve -> verify -> restore-test -> review -> dispose or retain`

## Roles

- **Record owner:** confirms business meaning and retention.
- **Repository maintainer:** maintains automation and resolves validation failures.
- **Preservation custodian:** performs fixity and restore checks.
- **Reviewer:** completes the annual conformance review.

One person may hold multiple roles in a small organization, but each event must identify the acting role.

## Automation boundary

The repository workflow validates public examples and evidence metadata. It must not ingest secrets, credentials, private documents, production databases, personal information, or unredacted configurations. Private archival packages belong in approved restricted storage and may publish only sanitized metadata or attestations.

## Release evidence

For every preservation release:

- create a versioned package directory;
- generate a deterministic SHA-256 manifest;
- validate metadata;
- record the source commit and release identifier;
- preserve dependency and restoration information;
- sign or attest the release when signing infrastructure is available;
- retain validation output with the package.

## Review cadence

- Continuous: pull-request validation.
- Quarterly: sampled fixity verification.
- Annually: conformance report and restoration test.
- Event-driven: migration, incident, custody transfer, legal hold, or major platform change.

## Claims

Passing repository validation demonstrates that specified controls produced evidence at a point in time. It is not, by itself, external certification or proof that every operational record is compliant.
