# WW.CX Operational Records Evidence Program

## Purpose

This program turns the repository records policy into reproducible evidence for public engineering records. It provides a safe model for controlled internal records without publishing private content or claiming external certification.

The governing policy remains [Records and Evidence Policy](../records-governance/RECORDS_EVIDENCE_POLICY.md). This document defines the operational evidence package layered beneath that policy.

## Evidence package

Each governed package contains:

1. a stable WWCX record identifier;
2. metadata conforming to `schemas/records-evidence.schema.json`;
3. one or more preserved objects addressed by portable relative paths;
4. a deterministic SHA-256 manifest covering the same objects;
5. provenance, retention, sensitivity, responsible-role, and preservation-event metadata;
6. restoration instructions and periodic restore-test evidence when the package is archival.

A sanitized working example is maintained in `examples/records-evidence/`.

## Lifecycle

`capture -> classify -> validate -> package -> preserve -> verify -> restore-test -> review -> retain, transfer, or dispose`

## Roles

- **Record owner:** confirms business meaning and retention.
- **Repository maintainer:** maintains validation automation and resolves failures.
- **Preservation custodian:** performs fixity and restoration checks.
- **Reviewer:** evaluates the evidence set and periodic conformance report.

One person may hold multiple roles in a small organization. Each preservation event must record both the acting agent and acting role.

## Automated validation

Validate a package directly:

```bash
python3 tools/validate_records_evidence.py \
  examples/records-evidence/example-record.json \
  --package-root examples/records-evidence \
  --manifest examples/records-evidence/manifest.sha256
```

Run positive and negative regression coverage:

```bash
python3 tests/validate_records_evidence_automation.py
```

The repository-wide GitHub Actions workflow runs the regression test on every pull request and push to `main`.

## Enforced controls

The validator rejects:

- missing required metadata or unsupported enumerations;
- non-UTC or malformed event timestamps;
- absolute, backslash-containing, empty-segment, current-directory, or parent-traversal paths;
- duplicate object or manifest paths;
- invalid sizes or SHA-256 values;
- files that are missing, leave the package root, or differ from the recorded size or digest;
- manifest entries that do not exactly match the record object set;
- destruction disposition while a legal hold is active;
- preservation events without an acting role.

## Automation boundary

Validation operates only on an explicitly selected package root. Public examples must be synthetic or sanitized. Private archival packages belong in approved restricted storage and may publish only safe metadata or attestations.

The workflow must not ingest credentials, private documents, production databases, search indexes, personal information, or unredacted configurations. It does not deploy, restart, migrate, or delete production data.

## Release evidence

For each preservation release:

- create a versioned package directory;
- validate its metadata and manifest;
- record the authoritative source revision and release identifier;
- preserve dependency and restoration information;
- retain validation output with the restricted or public package as appropriate;
- sign or attest the release when approved signing infrastructure is available.

## Review cadence

- **Continuous:** pull-request validation.
- **Quarterly:** sampled fixity verification.
- **Annually:** evidence review and restoration exercise.
- **Event-driven:** migration, incident, custody transfer, legal hold, or major platform change.

Use [the repository quality index](07-repository-quality-index.md) and [annual report template](templates/annual-conformance-report.md) as project review aids.

## Claims

Passing validation demonstrates that the specified package controls produced evidence at a point in time. It does not by itself prove production deployment, legal compliance, comprehensive organizational conformance, or external certification.
