# WW.CX Digital Archive — Business159 Omeka S Deployment

Status: source-ready bounded private-file deployment; not executed live on Business159.

## Purpose

`deploy/digital-archive/omeka/business159_omeka_deploy.py` provides a fail-closed shared-host deployment transaction for Omeka S 4.2.x. It intentionally stops before database creation, first-user creation, DNS, certificates, Apache routing, or public exposure.

Omeka's official installation documentation identifies the supported line as 4.2 and requires Linux, Apache with `AllowOverride All` plus `mod_rewrite`, MySQL 5.7.9+ or MariaDB 10.2.6+, and PHP 8.1+ with PDO, `pdo_mysql`, `mbstring`, and `xml`. A thumbnail backend such as ImageMagick/imagick or GD is expected for useful media operation.

## Authority boundary

The transaction may only:

- inspect PHP CLI/version/extensions and thumbnail support;
- inspect free storage;
- validate an already-extracted Omeka S 4.2.x release payload;
- reject symlinks, malformed payload structure, and divergent payload hashes;
- validate a caller-supplied `database.ini` without returning its path or values;
- copy each reviewed release into an isolated immutable release directory;
- maintain shared persistent `files/` media storage outside releases;
- maintain one shared private `database.ini` outside releases and refuse divergent replacement;
- atomically point `current` at the reviewed release; and
- preserve deployment evidence and pointer-only rollback.

It cannot create the MySQL/MariaDB database or user, discover or print credentials, create the first Omeka administrator, modify `public_html`, change DNS/certificates/Apache/authentication/firewall/cron, publish a site, or delete releases/media/database content during rollback.

## Release acquisition and hashes

Release acquisition is separate from deployment. Obtain the supported official Omeka S release through the reviewed operator/browser workflow and preserve the original download plus acquisition metadata outside the public document root.

The deployment script computes a deterministic **tree SHA-256** over the extracted payload's relative filenames and per-file hashes. Pass that hash back to `--expected-tree-sha256` for apply. This pins the extracted payload; it does not replace any checksum/signature published for the original downloaded archive.

A payload must look like an Omeka S distribution and expose a verifiable `4.2`/`4.2.x` version marker. Any symlink inside the acquisition payload fails closed.

## Persistent runtime split

Code releases and mutable archive state are deliberately separated:

```text
~/apps/wwcx-omeka-s/
  current -> releases/<HASH>-<STAMP>/
  releases/
  shared/
    config/database.ini
    files/
  evidence/
```

On deployment the pristine release's empty `files/` directory is replaced by a symlink to `shared/files`. `config/database.ini` is linked to `shared/config/database.ini` mode `0600`. Therefore uploaded media and database configuration survive release changes and pointer rollback.

If a shared `database.ini` already exists, the supplied runtime configuration must be byte-for-byte identical. The transaction refuses to overwrite a divergent database configuration; database credential rotation is a separate privileged operation.

## Runtime database configuration

The dedicated database and database user must already exist before deployment. Prepare `database.ini` only on an approved secret-handling surface; never paste its values into ChatGPT or commit it to Git.

The supplied file must be a regular non-symlink file, be inaccessible to group/other (`0600` recommended), and contain `user`, `password`, `dbname`, and `host`. Preflight reports only readiness, mode, size, and missing setting names—not secret values or the supplied secret path.

## Read-only preflight

```bash
python3 deploy/digital-archive/omeka/business159_omeka_deploy.py \
  --app-root ~/apps/wwcx-omeka-s \
  --payload /private/path/omeka-s-4.2.x \
  --expected-tree-sha256 <TREE_SHA256> \
  --database-ini /private/path/database.ini
```

Preflight verifies PHP 8.1+, required extensions, thumbnail capability, release structure/hash/version, private database configuration, storage, existing shared-config compatibility, and `current` pointer safety. It does not mutate the application root.

Because Business159 is shared hosting, filesystem inspection cannot prove `AllowOverride All`/`mod_rewrite`; rewrite policy therefore remains explicitly **unverified** until confirmed through the authenticated hosting control plane or private browser acceptance.

## Apply

```bash
python3 deploy/digital-archive/omeka/business159_omeka_deploy.py \
  --app-root ~/apps/wwcx-omeka-s \
  --payload /private/path/omeka-s-4.2.x \
  --expected-tree-sha256 <TREE_SHA256> \
  --database-ini /private/path/database.ini \
  --apply
```

Apply creates a fresh release directory, installs the shared runtime links, and atomically advances `current`. No web document-root or domain mapping is created. Evidence records the release hash and pointer state while explicitly recording that database values, database creation, first-admin creation, and public changes are absent.

## Rollback

```bash
python3 deploy/digital-archive/omeka/business159_omeka_deploy.py \
  --app-root ~/apps/wwcx-omeka-s \
  --rollback ~/apps/wwcx-omeka-s/evidence/<RUN>
```

Rollback changes only the `current` pointer to its prior target, or removes it when there was no prior release. Deployed releases, shared media, shared database configuration, and the database remain untouched.

## Remaining live gates

1. Reconnect an authenticated Business159 execution/browser path.
2. Recheck PHP CLI/extensions, storage, rewrite/AllowOverride behavior, and upload limits on the live account.
3. Create the dedicated Omeka database/user through the hosting control plane without exposing credentials in chat or Git.
4. Acquire and preserve the official current 4.2.x release, then compute/review the extracted payload tree hash.
5. Run private-file deployment and verify `/admin` only through a private/unrouted acceptance path.
6. Complete the first-user setup interactively; no password belongs in automation evidence.
7. Verify PHP CLI/background jobs, thumbnail generation, uploads, and backup/restore.
8. Keep any public hostname, reverse proxy, certificate, or publication decision separately gated.
