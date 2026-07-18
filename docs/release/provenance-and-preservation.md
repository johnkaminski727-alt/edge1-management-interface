# Provenance and Preservation

Status: Controlled document
Applies to: Edge1 Management Interface release artifacts

## Provenance

Each adopted release must be traceable end to end:

- the tag and commit SHA identify the exact source state;
- the release workflow run (`.github/workflows/release.yml`) identifies how
  the archive was produced;
- the checksums bind the distributed bytes to that run;
- the release record (`release-evidence.md`) binds all of the above to a
  named approver and date.

Authenticity rests on this chain, not on trust in any single copy. A copy
of an artifact found anywhere can be authenticated by recomputing its
SHA-256 and comparing against the release record.

## Preservation

Long-term preservation follows the WW.CX records and digital preservation
standard (`docs/records-management/WWCX-RECORDS-AND-DIGITAL-PRESERVATION-STANDARD.md`)
and the archival package standard
(`docs/records-management/04-archival-package-standard.md`):

- archival copies live in the Edge1 companion file archive with their
  checksums and a copy of the release record;
- fixity is verified on ingest, on any migration, and on the annual review
  cycle;
- formats are preservation-friendly by construction (tar/gzip source
  archives, plain-text records) — no format migration is anticipated, but
  any future migration must preserve the original alongside the migrated
  copy.

## Chain of custody

Movement of an archival copy (new storage location, restored copy,
handoff to another operator) is noted in the release record with date,
actor, and post-move fixity result.
