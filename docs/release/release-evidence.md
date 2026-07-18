# Release Evidence Requirements

Status: Controlled standard  
Owner: Repository maintainers

## Purpose

Define the minimum evidence needed to demonstrate that a release was built from an identified source state, passed required controls, and was preserved with sufficient information for later verification or reconstruction.

## Required evidence

Every adopted release record must include:

- release version and release date;
- source repository and exact commit SHA;
- annotated or otherwise protected release tag, when used;
- source archive and cryptographic checksum manifest;
- completed release checklist;
- validation and test results;
- workflow run or build record identifiers;
- generated artifact names, sizes, and checksums;
- release notes;
- approver and any documented exceptions;
- SBOM and provenance attestations when generated;
- preservation location and post-transfer checksum verification.

## Evidence quality rules

Evidence must be attributable, timestamped, internally consistent, and sufficient to distinguish the release from every other build. Screenshots may supplement records but should not replace machine-readable logs or manifests. Redact secrets and private data before retention. Do not alter raw evidence; append explanatory notes separately.

## Recommended release record layout

```text
edge1-management-interface-<version>-release-record/
  README.md
  release-manifest.json
  SHA256SUMS
  source/
  artifacts/
  sbom/
  provenance/
  validation/
  approvals/
  release-notes.md
  rollback/
```

## Release manifest fields

The manifest should record:

- project name;
- version and tag;
- commit SHA;
- build date in UTC;
- builder or workflow identity;
- workflow name and run identifier;
- artifact list with media type, byte size, and SHA-256 digest;
- SBOM and provenance filenames;
- validation summary;
- exceptions and disposition;
- preservation destination.

## Completion criteria

A release record is complete only when the artifact inventory matches the retained files, checksums have been independently reverified after transfer, required approvals are present, and unresolved exceptions are clearly identified.

## Evidence review template

- Release/version:
- Commit SHA:
- Tag:
- Workflow/run:
- Reviewer:
- Review date:
- Artifact inventory reconciled: Yes/No
- Checksums verified: Yes/No
- Required tests passed: Yes/No
- SBOM present or exception recorded: Yes/No
- Provenance present or exception recorded: Yes/No
- Secrets/private data review completed: Yes/No
- Preservation copy verified: Yes/No
- Exceptions:
- Final disposition: Accepted / Rejected / Superseded
