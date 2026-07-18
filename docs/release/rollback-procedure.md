# Release Rollback Procedure

Status: Controlled procedure  
Owner: Repository maintainers  
Applies to: Edge1 Management Interface releases

## Purpose

Provide a repeatable, auditable process for withdrawing, reverting, or superseding a release when validation, deployment, security, or operational evidence shows that the release should not remain in use.

## Rollback triggers

Initiate rollback review when any of the following occurs:

- release artifacts fail checksum, signature, provenance, or extraction verification;
- required tests or release gates were skipped, failed, or later found unreliable;
- a release contains secrets, private data, unsafe configuration, or unauthorized material;
- deployment causes material service degradation, data integrity risk, or security exposure;
- the released commit, tag, or archive cannot be reproduced from the retained evidence;
- maintainers determine that continuing use creates more risk than rollback.

## Decision authority

Artifact creation does not authorize deployment or rollback. A maintainer with repository administration authority records the rollback decision, its scope, and the evidence supporting it. Emergency action may precede full documentation when necessary to protect systems or data, but the record must be completed afterward.

## Procedure

1. Freeze further promotion of the affected release.
2. Record the release version, tag, commit SHA, artifact checksums, detection time, and reporter.
3. Preserve relevant logs and evidence without adding secrets or private data to the repository.
4. Identify the last known-good release and verify its retained checksums and source commit.
5. Select the safest action: withdraw artifacts, revert the release commit, redeploy the prior release, or publish a superseding fixed release.
6. Execute only bounded, reversible changes using the applicable deployment runbook.
7. Validate service health, expected functionality, configuration, and data integrity.
8. Update release notes and the release record with the outcome and any residual risk.
9. Open follow-up issues for root-cause correction and preventive controls.

## Validation checklist

- [ ] Affected release uniquely identified
- [ ] Last known-good release verified
- [ ] Rollback scope approved
- [ ] Backup or recovery path confirmed
- [ ] Rollback completed without unapproved data loss
- [ ] Health and smoke tests passed
- [ ] Evidence and timestamps retained
- [ ] Stakeholders notified as appropriate
- [ ] Corrective work tracked

## Rollback record

Record at minimum:

- decision date and decision maker;
- affected version, tag, and commit SHA;
- reason and triggering evidence;
- action taken and commands or automation used;
- validation results;
- final operational state;
- links to issues, pull requests, logs, and superseding releases.

Never place credentials, private keys, tokens, private documents, or unredacted production logs in the rollback record.
