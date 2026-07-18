# Release Rollback Procedure

Status: Controlled document
Applies to: Edge1 Management Interface source releases

## When to consider withdrawal

Withdraw or supersede a release when any of the following is discovered in a
published artifact: included credentials or private data, a security defect
exploitable from the artifact, a corrupted or non-reproducible archive, or a
checksum/manifest mismatch.

## Decision

1. Record who identified the problem, when, and the affected version(s).
2. Classify severity: privacy/security exposure (act immediately) versus
   functional defect (schedule a superseding release).
3. Decide: withdraw (remove the artifact) or supersede (publish a corrected
   version and mark the old one deprecated). Privacy and security exposures
   are withdrawn, not merely superseded.

## Execution

1. Remove or deprecate the affected GitHub release and its assets.
2. If a tag must be removed, record the tag name and SHA in the release
   record before deletion; never reuse a removed version number.
3. If private data was exposed, treat it as an incident: rotate any exposed
   secrets, and record the exposure window and viewers if determinable.
4. Publish a superseding release or a release-notes correction explaining
   the withdrawal in plain language.
5. Update the release record with the outcome and retain the withdrawn
   artifact privately (see `artifact-retention.md`) for evidence.

## Verification

- The withdrawn artifact is no longer downloadable.
- The release record documents cause, decision, execution, and outcome.
- Any replacement release passed the full `release-checklist.md`.
