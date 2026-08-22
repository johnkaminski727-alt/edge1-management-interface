# Omeka S on Business159

Status: deployment runbook prepared; no live install, database, domain, credential or routing change is performed by this source package.

Omeka's current 4.2 line requires Linux, Apache with rewrite support, MySQL/MariaDB, and PHP 8.1+ with PDO, `pdo_mysql`, `mbstring` and `xml`; Imagick or GD is useful for thumbnails. The Business159 cPanel environment was previously inspected and is compatible at the PHP/extension level, but those facts must be rechecked at deployment time.

## Safe deployment sequence

1. Recheck cPanel PHP version/extensions, Apache rewrite behavior, available disk and PHP CLI path.
2. Create a **dedicated** Omeka database/user using the hosting control plane. Never reuse a website database and never commit `database.ini`.
3. Download the current supported Omeka S 4.2 release from the official Omeka site and verify its published release metadata/checksum when available.
4. Preserve the pristine downloaded archive/hash as acquisition evidence outside the public document root.
5. Extract into an isolated application/document root; do not overwrite `public_html` or any existing site.
6. Populate `config/database.ini` only on the host with the dedicated runtime secret values.
7. Make only Omeka's required writable directories writable by the web process.
8. Verify `/admin`, PHP CLI/background jobs, thumbnail generation and file upload limits before adding data.
9. Complete the first-user setup interactively through the authenticated browser; never place the password in Git/chat.
10. Keep the site private/unrouted until authentication, backup/restore and exposure decisions are explicitly approved.

## Publication rule

Omeka S is the curated presentation/catalog layer. It may reference or display derivatives of authoritative records, but it does not silently become the sole authoritative home for original evidence.
