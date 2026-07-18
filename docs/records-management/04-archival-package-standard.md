# WW.CX Archival Package Standard

## Purpose

This standard defines a minimum archival information package for preserving significant WW.CX, Edge1, Big Bird, Private Library, website, infrastructure, and project records independently of the live working system.

## Package structure

```text
<package-id>/
  README.md
  manifest-sha256.txt
  metadata.json
  objects/
  documentation/
  preservation/
    events.jsonl
    fixity-history.jsonl
    transfer-receipt.md
```

## Required contents

`README.md` describes the package, scope, creator, authoritative source, exclusions, sensitivity, and restoration procedure.

`manifest-sha256.txt` contains a SHA-256 checksum for every file except the manifest itself. Paths must be relative, normalized, and sorted.

`metadata.json` records the required metadata profile, including package identifier, record class, retention rule, rights, provenance, format inventory, source commit or release, and responsible agents.

`objects/` contains the preserved records in their original or normalized preservation formats.

`documentation/` contains contextual material needed to understand, validate, render, or restore the records.

`preservation/events.jsonl` records preservation actions such as package creation, validation, virus scanning, format identification, migration, fixity checking, replication, restoration testing, and disposition review.

`preservation/fixity-history.jsonl` records the time, agent, algorithm, expected value, observed value, and result of each fixity check.

`preservation/transfer-receipt.md` documents the source, destination, package identifier, package size, transfer date, checksum verification, accepting custodian, and exceptions.

## Preservation events

Each event must record:

- event identifier;
- event type;
- UTC timestamp;
- responsible agent;
- affected object or package identifier;
- tool and version, when applicable;
- outcome;
- details or exception note.

## Fixity

SHA-256 is the minimum checksum algorithm. Fixity must be verified:

1. when the package is created;
2. after transfer to each preservation location;
3. at least annually;
4. before and after migration;
5. during restoration tests;
6. whenever storage corruption is suspected.

A failed check requires an incident record, comparison against independent replicas, documented recovery, and a new preservation event. The failed evidence must not be silently overwritten.

## Replication

Maintain at least three controlled copies for permanent or high-value records:

- one primary preservation copy;
- one independent local or organizational replica;
- one geographically or administratively separate replica.

At least one copy should be protected against routine alteration or deletion. Credentials and encryption keys must be managed separately from the packages they protect.

## Format guidance

Preserve original files whenever lawful and safe. Add normalized or open-format derivatives when needed for long-term access. Document every migration and retain the original unless a formally approved disposition decision permits otherwise.

Common preferred preservation formats include UTF-8 text, PDF/A for fixed documents when suitable, CSV plus schema for tabular data, JSON or XML with schemas for structured data, TIFF or PNG for lossless images, and standardized archival containers for audiovisual material.

## Validation and restoration

A package is accepted only after structure validation, metadata review, malware scanning where appropriate, checksum verification, and confirmation that representative objects can be opened or restored. Permanent packages require a documented restoration test at least annually or after material platform change.

## Authority

GitHub, production servers, shared hosting, and working databases are operational systems, not by themselves preservation repositories. The authoritative record location and preservation-copy locations must be declared in package metadata.
