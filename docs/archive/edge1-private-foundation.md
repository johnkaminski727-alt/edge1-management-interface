# WW.CX Digital Archive — Edge1 Private Foundation

Status: source-ready bounded bootstrap; not executed live on Edge1.

## Purpose

`deploy/digital-archive/edge1_private_foundation.py` turns the existing pinned Paperless-ngx and ArchiveBox Compose manifests into one auditable private bootstrap transaction. It is deliberately narrower than a general container installer or archive migration tool.

The transaction may only:

- validate the reviewed Compose sources;
- verify Docker + the Compose plugin are already available;
- verify Paperless secret files exist outside Git and have private permissions;
- verify at least 5 GiB of free storage remains on the filesystem that will host `/var/lib/wwcx-digital-archive`;
- reject unverified listeners on `127.0.0.1:8113` or `127.0.0.1:8114`;
- create the fixed private runtime directory tree;
- start the `wwcx-paperless` and `wwcx-archivebox` Compose projects;
- verify both loopback HTTP endpoints answer; and
- retain a deployment-state record for bounded rollback.

It does **not** install Docker, change package repositories, create DNS, certificates, Apache routes, firewall rules or authentication, ingest canonical records, create external accounts, submit ArchiveBox captures to Internet Archive, or expose a public listener.

## Fixed service boundary

Paperless remains pinned to `ghcr.io/paperless-ngx/paperless-ngx:3.0.5` on `127.0.0.1:8113`.

ArchiveBox remains pinned to `archivebox/archivebox:0.7.4` on `127.0.0.1:8114` with `PUBLIC_INDEX=False`, `PUBLIC_SNAPSHOTS=False`, `PUBLIC_ADD_VIEW=False`, and `SAVE_ARCHIVE_DOT_ORG=False`.

The script re-validates these source properties before every apply and rollback.

## Runtime secret boundary

Paperless requires two host-side secret files:

- database password;
- application secret key.

The script accepts only file paths. It never prints or records secret contents. Secret files must be regular, non-symlink files, at least 32 bytes long, readable by the invoking root operator, and inaccessible to group/other (`0600` is recommended).

No secret value belongs in Git, `.env` committed source, ChatGPT, a deployment record, or the Cookie Monster knowledge store.

## Read-only preflight

Preflight does not create directories, start containers or write deployment state:

```bash
python3 deploy/digital-archive/edge1_private_foundation.py \
  --paperless-db-password-file /path/to/runtime/db-password \
  --paperless-secret-key-file /path/to/runtime/secret-key
```

A blocked preflight returns machine-readable reasons such as:

- `docker-not-installed-or-not-on-path`;
- `docker-compose-plugin-unavailable`;
- missing/private-permission secret failures; or
- `insufficient-free-storage`.

A blocked runtime check is not permission to install Docker. Package/runtime installation remains a separate privileged host change.

## Apply

Apply is root-only and restricted to `/opt/edge1-management-interface`:

```bash
sudo python3 deploy/digital-archive/edge1_private_foundation.py \
  --paperless-db-password-file /path/to/runtime/db-password \
  --paperless-secret-key-file /path/to/runtime/secret-key \
  --apply
```

Before `up -d`, the script runs `docker compose config --quiet` for both projects, records whether either project was already running, and refuses an occupied loopback port unless the matching Compose project is already running.

Runtime data lives under:

```text
/var/lib/wwcx-digital-archive/
  paperless/
  archivebox/
  evidence/private-foundation/
```

No canonical archive material is copied into either application by this transaction. Real ingestion follows only after backup/restore and authority acceptance are separately verified.

## Verification

An apply is incomplete until both local HTTP endpoints respond:

```text
http://127.0.0.1:8113/
http://127.0.0.1:8114/
```

HTTP 2xx, 3xx and bounded 4xx responses count as process/application reachability. Public reachability is neither required nor tested.

The evidence directory records only source hashes, project lifecycle state, health results and rollback metadata. Secret contents and secret paths are excluded from emitted preflight state.

## Rollback

Rollback is intentionally non-destructive. It stops only a project that the recorded transaction first started when that project was not already running.

```bash
sudo python3 deploy/digital-archive/edge1_private_foundation.py \
  --paperless-db-password-file /path/to/runtime/db-password \
  --paperless-secret-key-file /path/to/runtime/secret-key \
  --rollback /var/lib/wwcx-digital-archive/evidence/private-foundation/<RUN>
```

The most recent recorded transaction may use `--rollback-last`.

Rollback uses `docker compose down` **without** `-v`. PostgreSQL data, Paperless media/data/export/consume, Valkey data, ArchiveBox data and evidence directories are preserved.

## Activation gates still outside this package

1. Docker/Compose installation or repair, if needed.
2. Creation and secure custody of Paperless runtime secret values.
3. Backup and restore acceptance before canonical document ingestion.
4. Creation of initial Paperless/ArchiveBox administrative accounts as required by the applications.
5. Any reverse proxy, DNS, certificate, authentication or public-route work.
6. Business159 Omeka S installation and database setup.
7. Zotero/Internet Archive interactive authentication or external publication.

Source readiness is not evidence that either service is live.
