# WW.CX Records and Digital Preservation Conformance Checklist

Use this checklist during project closure, major release, annual review, archival transfer, and before any disposition action.

## Governance

- [ ] A records custodian and business owner are identified.
- [ ] Applicable legal, contractual, privacy, tax, employment, and security requirements have been reviewed.
- [ ] The authoritative-copy location is declared.
- [ ] Roles for creation, approval, custody, preservation, access, and disposition are separated where practical.
- [ ] Exceptions are documented and approved.

## Capture and classification

- [ ] Official records are distinguished from drafts, convenience copies, and transitory material.
- [ ] Each record has a stable identifier and required metadata.
- [ ] The record class, sensitivity, retention rule, and retention trigger are assigned.
- [ ] Related records, approvals, source versions, commits, and pull requests are linked.
- [ ] Public derivatives are verified as sanitized and independently classified.

## Integrity and authenticity

- [ ] Version history is preserved.
- [ ] Material changes identify the responsible agent, date, purpose, and approval.
- [ ] SHA-256 fixity values exist for preserved objects.
- [ ] Checksums have been independently verified after transfer.
- [ ] Failed validations and corrective actions remain in the audit history.

## Preservation package

- [ ] Package structure conforms to `04-archival-package-standard.md`.
- [ ] Package README describes scope, provenance, restrictions, and restoration.
- [ ] Metadata is complete and machine-readable.
- [ ] The manifest covers every required package object.
- [ ] Preservation events and transfer receipt are present.
- [ ] Original formats are retained where lawful and safe.
- [ ] Normalized derivatives and migrations are documented.

## Storage and continuity

- [ ] Three controlled copies exist for permanent or high-value records.
- [ ] At least one copy is independently administered or geographically separate.
- [ ] At least one copy is protected from routine alteration or deletion.
- [ ] Encryption keys and credentials are stored separately.
- [ ] Annual fixity and representative restoration tests are scheduled.
- [ ] Recovery outcomes and exceptions are recorded.

## Access and privacy

- [ ] Access follows least privilege.
- [ ] Restricted records are excluded from public repositories.
- [ ] Access changes and exceptional disclosures are auditable.
- [ ] Personal and confidential information is minimized.
- [ ] Redaction preserves provenance without exposing protected content.

## Retention, holds, and disposition

- [ ] The retention trigger and elapsed period are confirmed.
- [ ] No legal hold, investigation, incident, audit, or unresolved business need applies.
- [ ] Permanent records have been transferred and verified before source deletion.
- [ ] Disposition is approved by the records custodian and business owner.
- [ ] Destruction is secure and proportionate to sensitivity.
- [ ] A disposition certificate records authority, scope, date, method, and responsible agent.

## Review result

Record the assessment as one of:

- **Conformant:** all applicable controls are implemented and evidenced.
- **Conformant with exceptions:** limited exceptions are documented, risk-accepted, and assigned corrective dates.
- **Not conformant:** material controls are missing or unverified; no compliance claim may be made.

A policy document alone is not evidence of operational conformance. Claims must be supported by completed manifests, metadata, checks, transfer receipts, restoration tests, custody records, and disposition evidence.
