# Release Artifact Retention

Status: Controlled standard  
Owner: Repository maintainers  
Applies to: Edge1 Management Interface release records and distributable artifacts

## Purpose

Define how release artifacts and supporting evidence are retained, verified, protected, reviewed, and ultimately disposed of.

## Retention classes

| Class | Examples | Minimum retention |
| --- | --- | --- |
| Permanent release record | Source archive, checksum manifest, release manifest, release notes, approvals, provenance record | Life of the project plus seven years |
| Reproducibility evidence | SBOM, build logs, validation output, workflow metadata, dependency lock files | Seven years |
| Operational evidence | Deployment and rollback records, incident references, exception approvals | Seven years |
| Temporary build output | Intermediate objects, caches, unsigned test packages | Until release acceptance plus 90 days |

A longer legal, contractual, preservation, or incident-hold requirement overrides these minimums.

## Required controls

- Store adopted release records in at least two administratively independent locations.
- Record SHA-256 digests for every retained artifact.
- Reverify checksums after each transfer and during periodic integrity review.
- Restrict write access to designated maintainers or records custodians.
- Keep immutable or versioned copies where the storage platform supports them.
- Do not retain secrets, credentials, private keys, production configuration, private documents, or unredacted sensitive logs.
- Preserve the exact source commit, tag, build identity, and artifact inventory.

## Naming and organization

Use `edge1-management-interface-<version>-release-record` for the top-level record. Filenames must be stable, descriptive, and reflected in the release manifest. Replacement files must receive a new version or explicit supersession record; never silently overwrite accepted evidence.

## Integrity review

At least annually, and after storage migration, a maintainer must:

1. reconcile the manifest against retained files;
2. recompute and compare checksums;
3. confirm that both preservation copies remain readable;
4. record missing, corrupt, or superseded material;
5. initiate restoration or exception handling when verification fails.

## Disposal

Temporary artifacts may be removed after their retention period when no hold applies. Permanent release records require documented maintainer approval before disposal. Disposal records must identify the material, reason, approving person, date, and method.

## Exceptions

Any deviation must identify the affected release, unavailable control, compensating measure, owner, approval, and target resolution date.