# WW.CX Digital Archive — Business159 Omeka S Deployment

Status: source-ready bounded private-file deployment; not executed live on Business159.

## Purpose

`deploy/digital-archive/omeka/business159_omeka_deploy.py` provides a fail-closed shared-host deployment transaction for Omeka S 4.2.x. It intentionally stops before database creation, first-user creation, DNS, certificates, Apache routing, or public exposure.

Omeka's official installation documentation identifies the current supported line as 4.2 and requires Linux, Apache with `AllowOverride All` plus `mod_rewrite`, MySQL 5.7.9+ or MariaDB 10.2.6+, and PHP 8.1+ with PDO, `pdo_mysql`, `mbstring`, and `xml`. A thumbnail backend such as ImageMagick/imagick or GD is also expected for useful media operation.

## Authority boundary

The transaction may only:

- inspect PHP CLI/version/extensions and available thumbnail support;
- inspect free storage;
- validate an already-extracted Omeka S 4.2.x release payload;
- reject symlinks, malformed payload structure, and divergent payload hashes;
- validate a caller-supplied `database.ini` without returning its path or values;
- copy the release into an isolated application release directory;
- install `config/database.ini` mode `0600`;
- make only the release `files/` directory writable within this package's private app tree;
- atomically point `current` at the reviewed release; and
- preserve deployment evidence and pointer-only rollback.

It cannot:

- create the MySQL/MariaDB database or user;
- discover or print database credentials;
- create the first Omeka administrator;
- modify `public_html`;
- change DNS, certificates, Apache/vhost configuration, authentication, firewall, cron, or external accounts;
- publish a site; or
- delete a release, Omeka files, or database content during rollback.

## Release acquisition and hashes

Release acquisition is separate from deployment. Obtain the supported official Omeka S release through the reviewed operator/browser workflow and preserve the original download plus its acquisition metadata outside the public document root.

The deployment script computes a deterministic **tree SHA-256** over the extracted payload's relative filenames and per-file hashes. Pass that tree hash back to `--expected-tree-sha256` for apply. This is an internal integrity pin for the extracted payload; it is not a substitute for any checksum or signature published for the original downloaded archive.

A payload must look like an Omeka S distribution and expose a verifiable `4.2`/`4.2.x` version marker. Any symlink inside the payload fails closed.

## Runtime database configuration

The dedicated database and database user must already exist before deployment. Prepare `database.ini` on the authenticated host or another approved secret-handling surface; never paste its values into ChatGPT or commit it to Git.

The script requires the supplied file to:

- be a regular non-symlink file;
- be inaccessible to group/other (`0600` recommended); and
- contain settings for `user`, `password`, `dbname`, and `host`.

Preflight reports only readiness, mode, size, and missing setting names. It does not return secret values or the secret file path.

## Read-only preflight

Example:

```bash
python3 deploy/digital-archive/omeka/business159_omeka_deploy.py \
  --app-root ~/apps/wwcx-omeka-s \
  --payload /private/path/omeka-s-4.2.x \
  --expected-tree-sha256 <TREE_SHA256> \
  --database-ini /private/path/database.ini
```

Preflight verifies PHP 8.1+, required extensions, thumbnail capability, release structure/hash/version, private database configuration, storage, and existing `current` path safety. It does not mutate the application root.

Because Business159 is shared hosting, filesystem inspection cannot prove the Apache vhost has `AllowOverride All` and `mod_rewrite`. The result therefore records rewrite policy as **unverified** even when all file-level checks pass. That boundary must be verified through the authenticated hosting control plane or private browser acceptance before any route is activated.

## Apply

Apply performs only private application-file deployment:

```bash
python3 deploy/digital-archive/omeka/business159_omeka_deploy.py \
  --app-root ~/apps/wwcx-omeka-s \
  --payload /private/path/omeka-s-4.2.x \
  --expected-tree-sha256 <TREE_SHA256> \
  --database-ini /private/path/database.ini \
  --apply
```

The release is copied to:

```text
~/apps/wwcx-omeka-s/releases/<tree-hash-prefix>/
```

and `~/apps/wwcx-omeka-s/current` is atomically pointed to that release. No web document-root or domain mapping is created by this action.

Deployment evidence records the release hash and pointer state while explicitly recording that database values, database creation, first-admin creation, and public changes are absent.

## Rollback

Rollback changes only the `current` pointer to its prior target, or removes `current` when there was no prior deployment:

```bash
python3 deploy/digital-archive/omeka/business159_omeka_deploy.py \
  --app-root ~/apps/wwcx-omeka-s \
  --rollback ~/apps/wwcx-omeka-s/evidence/<RUN>
```

The deployed release directory, `files/` data, and database remain untouched. This preserves evidence and makes rollback reversible.

## Remaining live gates

1. Reconnect an authenticated Business159 execution/browser path.
2. Recheck PHP CLI/extensions, storage, rewrite/AllowOverride behavior, and upload limits on the live account.
3. Create the dedicated Omeka database/user through the hosting control plane without exposing credentials in chat or Git.
4. Acquire and preserve the official current 4.2.x release, then compute/review the extracted payload tree hash.
5. Run private-file deployment and verify `/admin` only through a private/unrouted acceptance path.
6. Complete the first-user setup interactively; no password belongs in automation evidence.
7. Verify PHP CLI/background jobs, thumbnail generation, uploads, and backup/restore.
8. Keep any public hostname, reverse proxy, certificate, or publication decision separately gated.
