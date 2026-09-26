# Backup & Recovery console — first implementation (2026-09-26)

Status: **source committed on feature branch; NOT deployed to Edge1**.
Scope: localhost-only, read-only status API and a responsive appliance-style browser dashboard.

## Source
- `server/backup_recovery_server.py`: serves `/` and `/api/backups/status`.
- `src/web/backup-recovery/index.html`: dashboard with archive table and separated upload, integrity and restore-test metrics.
- `tests/validate_backup_recovery.py`: offline API/manifest validation tests.
- `tools/backup/import_rclone_listing.py`: bounded local importer of Dropbox metadata listings.
- `tests/validate_backup_import.py`: importer safety and no-false-claims tests.

## Operator-only local preview

Run on **Edge1** in a checkout of this branch (after review):

```bash
python3 tests/validate_backup_recovery.py
python3 server/backup_recovery_server.py --host 127.0.0.1 --port 8108
```

Open `http://127.0.0.1:8108/` through an approved authenticated private tunnel. Do **not** bind to a public interface or expose port 8108 through a reverse proxy until authentication, authorization and deployment reviews are completed.

The API reads sanitized JSON manifests from `/var/lib/edge1-backup-dashboard/manifests/` or `EDGE1_BACKUP_MANIFEST_DIR`. It does not inspect backup archives, access Dropbox, or run any backup or restore. It returns no records until an operator-controlled verified data source produces manifests.

## Manifest contract

One atomic JSON file per backup, maximum 64 KiB each. Example below is **synthetic** and MUST NOT be mistaken for a live recovery result.

```json
{
  "archive": "edge1-EXAMPLE.tar.gz.gpg",
  "created_at": "2026-09-26T03:00:00Z",
  "size_bytes": 13000,
  "upload": "uploaded",
  "integrity": "unknown",
  "restore_test": "unknown"
}
```

The only permissible status values are `verified`, `uploaded`, `failed`, `pending` and `unknown`. Set `integrity=verified` only after a recorded archive test/hash validation, and `restore_test=verified` only after documented isolated restore acceptance. No path, bucket key, credential, secret, or raw logs should appear in these manifests. Write temp file, fsync and rename into place after source evidence is complete. Directory permissions should restrict writes to a dedicated trusted local status producer; web-facing API remains read-only.


## Phase 2: Import upload evidence from the configured Dropbox remote

`tools/backup/import_rclone_listing.py` provides the first **upload-only** bridge. On **Edge1**, an authorized operator first obtains a metadata listing of the existing encrypted backup directory using the server's already-configured rclone remote (replace `REMOTE_NAME` with the actual verified rclone remote, not a guessed value):

```bash
# Run on Edge1, after verifying the remote's configured destination:
umask 077
rclone lsjson 'REMOTE_NAME:Edge1-Recovery/daily' --files-only > /tmp/edge1-dropbox-daily-listing.json
# Make a private status directory once (choose appropriate ownership for your service):
sudo install -d -m 0700 /var/lib/edge1-backup-dashboard/manifests
sudo python3 tools/backup/import_rclone_listing.py \
  --listing /tmp/edge1-dropbox-daily-listing.json \
  --manifest-dir /var/lib/edge1-backup-dashboard/manifests \
  --dry-run
# After confirming scope and results, repeat without --dry-run to import.
```

If rclone is not installed/configured, inventory the current backup uploader rather than installing or replacing it blindly. The importer accepts *only* filenames matching `edge1-YYYYMMDDTHHMMSSZ.tar.gz.gpg` from the requested listing. It intentionally does not overwrite existing manifests or mark archive integrity or restoration as verified. Treat a listing as evidence reported by the operator-supplied rclone command, not an independent Dropbox API attestation. The operator should delete the temporary listing using ordinary secure file-handling policy once it is no longer needed.

The archive name's UTC timestamp is shown as the backup's `created_at`; the Dropbox listing's modification timestamp is not currently captured. This is not a scheduler health measurement, and older archives in a current listing do not establish a nightly run.

**Do not enable automatic scheduling of the importer** until the actual Edge1 backup timer/job and rclone destination are inventoried, and a dedicated service account, restrictive manifest directory and stale-backup alert threshold are defined. No backup or restoration operations are initiated by this bridge.

## Live integration gates

1. Inventory actual Edge1 backup timers and jobs, and inspect encrypted archive contents **without posting secrets to GitHub**.
2. Define an authenticated local producer for post-run manifests: scheduler result, exact archive checksum, encrypted archive size, Dropbox upload ID/confirmation, failure reason code (not raw logs), and evidence pointer kept locally. Verify Dropbox directly through an approved credentialed server-side integration; do not embed Dropbox tokens in browser code.
3. Define coverage manifests for system configuration, network policies, Chrony, VPN peers, Big Bird AI gateway, private-library SQLite snapshot, application databases, deployment definitions and securely stored secret recovery.
4. Create a documented restore trial into an isolated environment with independent integrity checks. Publish only a sanitized pass/fail and timestamp to the dashboard.
5. Add role-based operator actions only after authorization, backup validation, rollback and out-of-band access have been acceptance-tested.

Existing `deploy/digital-archive/backup_restore_acceptance.py` is a separate local restore-acceptance gate for digital archive workloads. Its successful local run must not be represented as Dropbox off-site confirmation. Integration must preserve that distinction.

## Security and claims

This is UI source, not production deployment or proof that Edge1 is restorable. The public repository must contain only sanitized source, synthetic fixtures and non-sensitive documentation. Private manifests belong on Edge1. A failed status API or empty directory must display **unknown**, never healthy. A successful upload cannot automatically imply successful checksum verification or restoration.
