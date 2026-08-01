# Asterisk `res_odbc.conf` Path Gate Acceptance — 2026-08-01

## Evidence

- Host: `edge1.ww.cx`
- Operator-run evidence directory: `/var/lib/wwcx-deployment-evidence/asterisk-res-odbc-path/20260801T044310Z`
- Audit file: `/var/lib/wwcx-deployment-evidence/asterisk-res-odbc-path/20260801T044310Z/audit.txt`
- Audit SHA-256: `83c9a432d74bdc7a03153dbca36a94d6e463695e1672fa45baf4d8e74346c31a`
- Exit code: `0`
- Warnings: `0`
- Failures: `0`

## Accepted findings

`/etc/asterisk/res_odbc.conf` is a symbolic link. Its `0777` entry mode is normal symlink metadata and is not the effective configuration permission.

The link resolves to:

```text
/var/www/html/admin/modules/core/etc/res_odbc.conf
```

The effective target is:

- a regular file;
- mode `0644`;
- owned by `asterisk:asterisk`;
- SHA-256 `0cc2cdc38479c3b22033156732e2d82f2ec4c9b138dd711955e6df5f79b88ad8`;
- attributed to package `freepbx17`.

No permission or ownership correction is required. The audit did not print configuration contents or credentials.

## MariaDB hardening gate

This closes the final file-permission ambiguity identified during the MariaDB loopback socket preflight. Together with the accepted endpoint and transport evidence, it supports a controlled change that preserves both MariaDB Unix sockets and restricts TCP `3306` to IPv4 and IPv6 loopback.

UCP TCP `8001` and `8003` remain explicitly outside the MariaDB change.

No service restart, socket override installation, daemon reload, database query, grant or schema change, FreePBX/PM2 mutation, listener change, firewall change, call, CAP feed or traffic change occurred during this audit.
