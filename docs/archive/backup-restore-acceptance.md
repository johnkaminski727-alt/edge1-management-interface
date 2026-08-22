# WW.CX Digital Archive — Backup and Restore Acceptance

Status: source-ready restore-acceptance harness; not executed live on Edge1.

## Purpose

The Digital Archive architecture requires backups to be proven by restore, not merely copied. `deploy/digital-archive/backup_restore_acceptance.py` implements that gate for the private Paperless-ngx and ArchiveBox working layers without touching canonical source records or public routing.

Paperless-ngx documents `document_exporter` as a complete export of documents, thumbnails, metadata, settings, and database contents, and restores that export with `document_importer`. Paperless also warns that exporter/importer compatibility is version-specific, so the restore harness uses the same pinned Paperless image as the source deployment.

ArchiveBox documents its complete collection state as the `data/` directory. The harness snapshots that directory as a unit and validates a restored copy with the same pinned ArchiveBox image and networking disabled.

## Scope and authority

This package may:

- require the Paperless consume queue to be empty before and immediately after export;
- run Paperless `document_exporter` inside the fixed private Compose project;
- briefly stop only the ArchiveBox application container while its data directory is snapshotted, then restore its prior running state;
- create SHA-256 manifests under `/var/lib/wwcx-digital-archive/backups`;
- verify backup archive path safety and hashes;
- restore Paperless into a unique disposable no-port Compose project on an **internal-only Docker network** using generated ephemeral restore-only credentials;
- run Paperless `document_importer` against the restored export;
- require successful teardown of the disposable Paperless stack before restore acceptance can pass;
- validate ArchiveBox from an extracted backup copy using `docker run --network none ... status`; and
- preserve restore-test state/evidence for inspection.

It cannot alter canonical source documents, expose a public listener, change DNS/certificates/Apache/authentication/firewall, use production Paperless secrets in the disposable restore target, delete backup sets/restore evidence, delete Docker volumes with `-v`, or claim a same-disk backup is an off-host/durable backup.

## Read-only preflight

```bash
python3 deploy/digital-archive/backup_restore_acceptance.py \
  --paperless-db-password-file /path/to/runtime/db-password \
  --paperless-secret-key-file /path/to/runtime/secret-key
```

Preflight checks the repository, Docker/Compose availability, runtime data/export roots, the Paperless consume root, and private secret-file paths. A missing/unsafe consume root or any pending file in the consume queue blocks backup creation. It returns `off_host_backup_created=false` because this package only creates the local verified backup set used for restore acceptance.

The empty-queue check is a minimum quiescence gate, not proof that every possible interactive/API write is impossible. Run a production backup during a controlled maintenance/quiescent window. The snapshot checks the consume queue both before and immediately after `document_exporter` so queued intake cannot silently overlap the accepted export.

## Create a backup set

```bash
sudo python3 deploy/digital-archive/backup_restore_acceptance.py \
  --paperless-db-password-file /path/to/runtime/db-password \
  --paperless-secret-key-file /path/to/runtime/secret-key \
  --snapshot
```

The backup set is written under:

```text
/var/lib/wwcx-digital-archive/backups/backup-<STAMP>-<PID>/
  manifest.json
  paperless-export.tar.gz
  archivebox-data.tar.gz
```

Paperless export data is produced by `document_exporter --no-progress-bar` into its private export mount before packaging. ArchiveBox is stopped only if it was running, its full data directory is archived, and the application container is immediately started again in a `finally` path.

`manifest.json` records fixed source image versions, file byte counts and SHA-256 hashes, plus `paperless_consume_queue_empty=true`. It explicitly records that Paperless secret values are absent and that no off-host copy has been made.

## Restore acceptance

```bash
sudo python3 deploy/digital-archive/backup_restore_acceptance.py \
  --restore-check /var/lib/wwcx-digital-archive/backups/backup-<STAMP>-<PID>
```

Before any restore action, the harness verifies both backup SHA-256 hashes and safely extracts archives with path/link traversal rejection.

### Paperless

A unique disposable Compose project is generated beneath `/var/lib/wwcx-digital-archive/restore-tests`. It:

- uses the same pinned Paperless/PostgreSQL/Valkey images as the private service baseline;
- exposes **no host ports**;
- attaches all three restore services only to a Docker network declared `internal: true`, preventing external egress while preserving DB/broker communication;
- uses fresh random restore-only database and application secrets kept only in the subprocess environment;
- bind-mounts the restored exporter payload read-only at `/restore`; and
- invokes `document_importer /restore --no-progress-bar` once the importer CLI is ready.

The disposable stack is then stopped with ordinary `docker compose down`; no `-v` deletion is used and restore data directories remain as evidence. **Cleanup is part of acceptance**: if the disposable stack cannot be brought down successfully, the restore result is `fail` even if import itself succeeded.

### ArchiveBox

The restored ArchiveBox copy is checked using the same pinned ArchiveBox image with `--network none`. Only `archivebox status` is invoked against the restored data mount.

Acceptance is `pass` only if Paperless import succeeds, the disposable Paperless stack cleans up successfully, and ArchiveBox status succeeds. Evidence records `restore_network_external_egress=false`, `production_projects_changed=false`, and that ephemeral restore secrets were not recorded.

## What this proves—and what it does not

A successful run proves that the local backup set is hash-consistent and that both application-layer restore procedures work against isolated copies with the pinned software versions.

It does **not** prove disaster recovery from Edge1 loss because the verified backup set remains on Edge1. After restore acceptance passes, the backup set or an equivalent authoritative backup must be copied to a separately governed durable/off-host destination, with its manifest/hash retained and the destination's retention/access policy documented. That off-host publication/storage action is intentionally outside this harness.

## Live gates

1. Paperless and ArchiveBox private services must first be installed and healthy.
2. Schedule a quiescent backup window and require an empty Paperless consume queue.
3. Run backup plus isolated restore acceptance before any canonical document intake.
4. Preserve the first successful acceptance evidence as the initial recovery baseline.
5. Establish the separately governed off-host backup destination and retention policy.
6. Repeat restore acceptance after material version, schema, storage-layout, or backup-procedure changes.
