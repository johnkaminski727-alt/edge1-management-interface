# WW.CX Records and Digital Preservation Standard

**Standard ID:** WWCX-RM-001  
**Version:** 1.0  
**Status:** Approved baseline  
**Owner:** Christmas Island Worldwide  
**Review cycle:** Annual and after material legal, technical, or organizational change

## 1. Purpose

This standard establishes the minimum controls for creating, capturing, maintaining, preserving, retrieving, transferring, and disposing of WW.CX business and technical records. It is designed to align operational practice with the principles of ISO 15489, trustworthy digital preservation, and PREMIS-style preservation metadata without claiming third-party certification.

## 2. Scope

This standard applies to records created or received through WW.CX, Edge1, Big Bird, the Private Library, GitHub repositories, websites, shared hosting, administrative systems, and related infrastructure projects.

It applies to source code, decisions, approvals, architecture records, runbooks, registers, reports, logs selected for retention, releases, deployment evidence, correspondence captured as records, and archival packages.

Secrets, credentials, private databases, personal information, and production-only material must remain in approved restricted systems and must not be copied into public repositories.

## 3. Governing principles

Records must be:

- authentic: attributable to a known person, system, or process;
- reliable: complete enough to support the business activity they document;
- integral: protected from unauthorized alteration or deletion;
- usable: discoverable, readable, and understandable for the required retention period;
- classified: assigned a record class, sensitivity, and retention rule;
- traceable: linked to provenance, related records, and preservation events;
- reviewable: subject to documented approval, hold, transfer, or disposition controls.

## 4. Roles

### Records owner

The business owner determines record value, sensitivity, authoritative-copy location, and retention class.

### Records custodian

The custodian maintains capture procedures, metadata, fixity evidence, access controls, preservation copies, review schedules, and disposition evidence.

### System owner

The system owner ensures that applications and repositories can export records with sufficient context and metadata.

### Contributors and automation

People and automated agents must use approved locations, sanitized public examples, attributable commits, and reversible workflows. Automation may prepare records and packages but may not authorize destruction, override a legal hold, or silently replace an authoritative record.

## 5. Authoritative copies

Every managed record series must designate one authoritative-copy location. GitHub may be authoritative for public source and public documentation, but it is not the sole preservation location. Restricted operational records remain authoritative in the approved internal system or Private Library collection.

An archival package is a preservation copy, not automatically the live authoritative copy. Package metadata must identify its source system, source reference, export time, and responsible agent.

## 6. Record capture

A record is captured when it is placed in an approved repository with:

- a stable identifier;
- title and description;
- creator or originating system;
- creation or capture date in UTC;
- record class and sensitivity;
- authoritative-copy designation;
- retention rule;
- provenance and related-record references;
- format and checksum information where packaged.

Commits, pull requests, signed approvals, issue decisions, release tags, audit records, and approved register entries may form part of the record context.

## 7. Classification and sensitivity

Records must use a class from `RETENTION-SCHEDULE.md` or an approved extension.

Sensitivity values are:

- `PUBLIC` — intentionally public;
- `INTERNAL` — business use, not public;
- `CONFIDENTIAL` — restricted operational, personal, financial, or security-related information;
- `RESTRICTED` — secrets, credentials, privileged material, or data whose disclosure could cause significant harm.

Public repositories may contain only `PUBLIC` records and sanitized examples derived from higher classifications.

## 8. Retention, holds, and disposition

Retention follows `RETENTION-SCHEDULE.md`. The retention clock begins at the trigger stated for the class.

A legal, regulatory, audit, investigation, security, or preservation hold suspends disposition. Holds must identify scope, authority, start date, custodian, and release authorization.

Disposition requires documented review and authorization. Destruction must produce a disposition certificate containing record class, covered identifiers, date range, method, authorization, date, and exceptions. Permanent records are transferred to the designated preservation repository rather than destroyed.

## 9. Preservation packages

Preservation packages must follow `ARCHIVAL-PACKAGE-SPECIFICATION.md` and include:

- preserved content;
- inventory;
- SHA-256 fixity manifest;
- descriptive and administrative metadata;
- preservation-event log;
- package-level README;
- validation result.

Packages must be stored in at least two independently managed locations when operationally feasible. At least one copy must be outside the source system.

## 10. Fixity and integrity

SHA-256 is the baseline fixity algorithm. Checksums must be generated after capture and verified:

- after transfer;
- after restoration;
- before and after format migration;
- at least annually for permanent packages;
- after suspected corruption or unauthorized change.

Failures must be logged as preservation events and investigated. A damaged copy must not overwrite a known-good copy.

## 11. Preservation metadata

Metadata follows `MINIMUM-METADATA-PROFILE.md`. Preservation events must record event type, timestamp, agent, affected object, outcome, and supporting detail. Event types include capture, validation, checksum generation, fixity check, transfer, replication, restore test, migration, access change, hold, hold release, and disposition.

## 12. Formats and migration

Open, documented, widely supported formats are preferred for long-term records. Original bitstreams must be retained when lawful and practical. Normalized or migrated copies must remain linked to the original and must document tool, version, date, agent, validation, and checksum changes.

## 13. Access and privacy

Access is least-privilege and based on sensitivity. Public documentation must not reveal credentials, private records, personal information, production databases, search indexes, or unredacted security diagnostics.

Redaction must preserve an unredacted authoritative copy in the approved restricted system when retention is required. The public derivative must identify that it is sanitized or redacted.

## 14. Backup and preservation distinction

Backups support operational recovery. Preservation copies support long-term authenticity, integrity, context, and usability. A backup alone does not satisfy this standard.

## 15. Audit and review

The records custodian must conduct an annual review covering:

- authoritative-copy designations;
- retention schedule currency;
- open holds;
- package validation and fixity results;
- restore-test evidence;
- access controls;
- disposition actions;
- exceptions and corrective actions.

Conformance statements must describe scope and evidence. They must not imply certification by ISO, NARA, the Library of Congress, or another external body unless such certification has actually been obtained.

## 16. Exceptions

Exceptions require documented risk, scope, compensating controls, owner approval, expiration date, and review date. Emergency exceptions must be reviewed promptly after the event.

## 17. Adoption

This version establishes the WW.CX baseline. Existing records should be brought under control according to risk and value, prioritizing permanent project records, approvals, architecture decisions, release evidence, security records, and unique historical materials.
