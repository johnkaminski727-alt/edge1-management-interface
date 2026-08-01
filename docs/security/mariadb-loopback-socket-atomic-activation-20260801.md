# MariaDB Loopback Socket Atomic Activation — 2026-08-01

## Status

**Prepared and validated in the repository; not yet run on Edge1.**

The operator is:

```text
tools/security/apply_mariadb_loopback_socket_hardening.sh
```

It applies the approved `mariadb.socket` drop-in as one bounded conditional production change and automatically restores the prior drop-in state if any required verification fails.

## Preconditions enforced by the operator

- Host must be `edge1.ww.cx`.
- The process must run as root through the approved sudo path.
- `EDGE1_ALLOW_CONDITIONAL=1`, `--apply`, and a timestamped evidence directory are required.
- The candidate drop-in must match SHA-256 `c5365e2d9bd882fcf62a8676b98f8f996094c5b5e45572fe9a0244b7f4f32fea`.
- The MariaDB loopback preflight must pass immediately before mutation.
- The `res_odbc.conf` effective-path gate must pass immediately before mutation.
- Asterisk must report zero active channels and zero active calls.

## Bounded mutation

The operator changes only:

```text
/etc/systemd/system/mariadb.socket.d/10-loopback-only.conf
```

It then performs:

1. `systemctl daemon-reload`;
2. `systemd-analyze verify mariadb.socket mariadb.service`;
3. one controlled stop/start of `mariadb.service` and `mariadb.socket`.

It does not change database contents, grants, schemas, credentials, UCP configuration, FreePBX configuration, Asterisk configuration, PM2, firewall, WireGuard, packages, calls, CAP feeds, or external traffic.

## Required success state

- MariaDB TCP `3306` listens on `127.0.0.1` and `::1` only.
- No wildcard TCP `3306` listener remains.
- `/run/mysqld/mysqld.sock` and `@mariadb` remain present.
- `mariadb.socket` and `mariadb.service` are active.
- UCP TCP `8001` and `8003` remain present and unchanged.
- The local UCP Node client reconnects to MariaDB over loopback within 30 seconds.
- Asterisk health checks remain available.

## Automatic rollback

If installation, systemd verification, restart, listener verification, Unix-socket verification, UCP listener verification, or UCP-to-MariaDB reconnection fails, the operator:

1. stops the MariaDB service/socket pair;
2. restores the prior drop-in or removes the new drop-in if none existed;
3. reloads systemd;
4. verifies the restored units;
5. restarts MariaDB;
6. captures rollback evidence.

A rollback failure exits with status `2` and must be treated as an immediate operator incident.
