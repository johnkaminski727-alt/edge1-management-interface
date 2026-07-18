# Artifact Retention

Status: Controlled document
Applies to: Edge1 Management Interface release artifacts and evidence

## Retention periods

| Item | Retention |
| --- | --- |
| Released source archives and checksums | Life of project + 2 years |
| Release evidence records | Life of project + 2 years |
| Withdrawn artifacts (kept privately as evidence) | 2 years after withdrawal |
| Release candidate builds never adopted | Until superseded, then discard |

These periods align with the repository records retention schedule in
`docs/records-management/02-records-retention-schedule.md`; where they
conflict, the records schedule governs.

## Storage and fixity

- Primary copy: the GitHub release assets attached to the tagged release.
- Secondary copy: the Edge1 companion file archive (per the repository
  boundary, large binaries never live in this git repository).
- Each stored artifact keeps its SHA-256 checksum beside it; verify fixity
  when a copy is moved, restored, or annually per the archival package
  standard (`docs/records-management/04-archival-package-standard.md`).

## Disposal

Discarded artifacts are deleted from all storage locations and the disposal
is noted in the release record. Withdrawn-for-privacy artifacts are securely
deleted at the end of their retention period; the record of the withdrawal
itself is retained.
