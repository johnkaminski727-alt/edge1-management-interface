# Release Documentation Package

Status: Draft controlled package  
Owner: Repository maintainers  
Review cycle: At least annually and before each major release  
Applies to: Edge1 Management Interface source releases

## Purpose

This directory is the authoritative index for release preparation, evidence, verification, preservation, rollback, and communication records. A release is not complete merely because an archive was produced; it is complete only when the required evidence has been reviewed and retained.

## Controlled documents

| Document | Purpose | Required for release |
| --- | --- | --- |
| [`../release-engineering.md`](../release-engineering.md) | Workflow behavior and release procedure | Yes |
| [`release-checklist.md`](release-checklist.md) | Pre-release, build, verification, and closure controls | Yes |
| [`rollback-procedure.md`](rollback-procedure.md) | Decision and execution guidance for withdrawing or reverting a release | Yes |
| [`release-evidence.md`](release-evidence.md) | Evidence package requirements and record template | Yes |
| [`artifact-retention.md`](artifact-retention.md) | Retention, fixity, storage, and disposal requirements | Yes |
| [`security-release-policy.md`](security-release-policy.md) | Security gates, secret handling, dependency review, and SBOM expectations | Yes |
| [`provenance-and-preservation.md`](provenance-and-preservation.md) | Provenance, authenticity, fixity, and archival package guidance | Yes |
| [`release-notes-template.md`](release-notes-template.md) | Standard release communication template | Yes |

## Release record convention

For each adopted release, create a durable release record outside the source tree or in an approved records repository. Use a directory or package name of the form:

`edge1-management-interface-<version>-release-record`

The record should contain the release manifest, checksums, source archive, SBOM when generated, workflow evidence, completed checklist, release notes, approvals, exceptions, and any rollback record.

## Control rules

- Do not place credentials, private keys, tokens, production configuration, private documents, or unredacted logs in a release package.
- Record exceptions explicitly; do not silently waive a required control.
- Preserve the exact commit SHA and tag used to build the release.
- Verify checksums after every transfer to a preservation location.
- Keep deployment authorization separate from artifact creation.
- Review this package whenever the release workflow or repository validation process changes.

## Revision history

| Date | Change | Author |
| --- | --- | --- |
| 2026-07-18 | Established controlled release documentation package | Repository maintainers |
