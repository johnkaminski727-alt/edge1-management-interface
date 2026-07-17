# Private Library Backup Runbook

Date: 2026-07-17
Classification: internal

## Purpose

Create a compressed backup of the Big Bird private library SQLite database for
handoff and recovery planning.

## Backup Location

```text
/var/backups/bigbird-ai-library
```

This path is intentionally outside the git repository.

## Create Backup

```bash
cd /opt/edge1-management-interface
sudo tools/handoff/create_private_library_backup.sh
```

The script:

1. Creates a restricted backup directory.
2. Uses Python's SQLite backup API to make a consistent copy.
3. Compresses the copy with gzip.
4. Writes a SHA-256 manifest.
5. Restricts backup file permissions.

## Verify Backup

```bash
sudo sha256sum -c /var/backups/bigbird-ai-library/<manifest>.sha256
```

Use the exact manifest path printed by the backup script.

## Handling Rules

- Do not commit the private library backup into git.
- Do not place the backup under `public_html`.
- Keep the backup on encrypted or access-controlled storage.
- Treat the archive as internal sensitive operational data.

