# Edge1 Apache deployment fragments

These fragments are repository-owned inputs for bounded Edge1 Apache changes. Live deployment is backup-first, config-tested, narrowly scoped, and followed by functional verification.

## Operations Center SNMP handoff AutoIndex hardening

`edge1-status-operations-center-no-index.conf` disables Apache directory indexing only for:

`/var/www/edge1-status/operations-center`

It does not alter the authenticated `/edge1-ops/snmp/` route, listener bindings, authentication/cookie behavior, the broader `/edge1-status/` tree, or Store Admin.

The accepted Edge1 live form on 2026-08-20 is a root-owned mode-0644 regular file at:

`/etc/apache2/conf-enabled/edge1-status-operations-center-no-index.conf`

Its content must match the repository fragment exactly. The accepted live SHA-256 was:

`f35f99db0f2a3429437502e5f9907cd7f4e9f7d90c0b12eab7a52eae90d991f3`

### Backup-first deployment

From an inspected, authorized Edge1 checkout, preserve any existing target before replacement and record its hash. Then install only the reviewed fragment:

```bash
sudo install -m 0644 \
  deploy/apache/edge1-status-operations-center-no-index.conf \
  /etc/apache2/conf-enabled/edge1-status-operations-center-no-index.conf
sudo apachectl -t
sudo systemctl reload apache2.service
```

Do not reload Apache if `apachectl -t` fails. If validation after reload fails, restore the recorded prior target (or remove the newly introduced fragment when none existed), run `apachectl -t`, and reload Apache again.

### Required verification

After deployment confirm:

```text
/edge1-status/operations-center/ -> 403 (or another explicit non-index response)
/edge1-status/operations-center/snmp.html -> 200 authentication handoff
/edge1-ops/snmp/ without a session -> 401
```

Also confirm the directory response does not contain `Index of /edge1-status/operations-center`, Apache remains active, `edge1-security-auth.service` remains active, TCP 8112 and 8787 remain loopback-only, and UDP 161/162 remain absent unless a separately approved SNMP network change exists.

This hardening is intentionally independent of `deploy/operations-center/publish.sh`, which publishes the public Operations Center files but does not install or reload Apache configuration.
