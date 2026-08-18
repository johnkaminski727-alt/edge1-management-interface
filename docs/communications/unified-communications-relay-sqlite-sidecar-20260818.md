# Unified Communications Relay SQLite sidecar sandbox evidence — 2026-08-18

## Live finding

The Relay database `/var/lib/wwcx-comms/comms.sqlite3` is SQLite WAL mode and remains authoritative at mode `0600`, owner/group `wwcx-comms:wwcx-comms`.

Phase 14H showed that a direct `wwcx-comms:wwadmin` read created the SQLite `-wal` and `-shm` sidecars before the transient read-only sandbox was exercised. The subsequent read-only sandbox therefore passed only after those sidecars already existed; it did not reproduce the original first-open condition.

The prior corrected persistent unit reached `sqlite3.connect(...mode=ro)` but failed on the first SELECT while the source directory was mounted read-only and no sidecars existed. No snapshot was created. This is consistent with SQLite WAL readers needing directory access to create/open shared-memory state even when the database file itself is read-only.

## Least-privilege correction

The snapshot service keeps:

- `User=wwcx-comms`
- `Group=wwadmin`
- `/var/lib/wwcx-comms/comms.sqlite3` explicitly read-only inside the unit namespace
- `/var/lib/wwcx-comms` writable only inside the unit namespace so SQLite can maintain `comms.sqlite3-wal` / `comms.sqlite3-shm`
- `/var/lib/wwcx-communications-workspace` as the only other writable runtime path

Host filesystem ownership and mode of the authoritative database are unchanged. The generator continues to open the database with `mode=ro` and `PRAGMA query_only=ON`.

## Safety

This change does not alter Relay ingestion, database schema, database permissions, communications traffic, public listeners, or mutation authority. The workspace remains metadata-only and read-only.
