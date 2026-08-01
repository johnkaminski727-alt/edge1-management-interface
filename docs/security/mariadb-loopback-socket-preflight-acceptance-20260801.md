# MariaDB Loopback Socket Preflight Acceptance — 2026-08-01

## Evidence

- Host: `edge1.ww.cx`
- Evidence directory: `/var/lib/wwcx-deployment-evidence/mariadb-loopback-socket-preflight/20260801T042329Z`
- Audit file: `/var/lib/wwcx-deployment-evidence/mariadb-loopback-socket-preflight/20260801T042329Z/audit.txt`
- SHA-256: `48ee4aca12b05bc083fc59eaa73455227ea63197ea7985c5abb606c4ec3643ac`
- Exit code: `0`
- Warnings: `0`
- Failures: `0`

## Accepted findings

- The candidate `mariadb.socket` drop-in hash is `c5365e2d9bd882fcf62a8676b98f8f996094c5b5e45572fe9a0244b7f4f32fea`.
- The current MariaDB socket contract retains `@mariadb`, `/run/mysqld/mysqld.sock`, and wildcard TCP `3306`.
- Exactly one logical MariaDB TCP relationship was observed: FreePBX UCP Node as the client and MariaDB as the server.
- Both endpoint rows were loopback scoped and `non_loopback_count=0`.
- FreePBX, Asterisk realtime, and ODBC transport candidates support loopback or Unix-socket access.
- UCP TCP `8001` and `8003` remain direct browser WebSocket listeners and are outside this hardening change.

## Remaining gate

`/etc/asterisk/res_odbc.conf` was reported as mode `0777`, 50 bytes, and transport scope unresolved. That is commonly symlink metadata, but the preflight did not record its file type or resolved target.

Before installing the MariaDB socket drop-in:

1. record the entry type and link target;
2. record the resolved target type, owner, group, mode, and SHA-256;
3. fail if the effective regular file is group- or world-writable;
4. do not print configuration contents or credentials.

The focused read-only audit is:

```text
tools/security/asterisk_res_odbc_path_audit.sh
```

## Decision

The MariaDB listener design is technically eligible for controlled loopback-only activation once the focused ODBC path audit passes. Activation remains a conditional production change requiring the existing rollback runbook, immediate service and listener verification, and rollback on any consumer failure.
