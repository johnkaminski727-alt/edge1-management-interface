# MariaDB Loopback Hardening Verification Incident — 2026-08-01

## Scope

This record covers the failed Edge1 activation attempt and the completed restoration of the prior MariaDB socket contract. It does not claim that loopback-only hardening has been activated.

## Evidence

- Host: `edge1.ww.cx`
- Failed activation evidence: `/var/lib/wwcx-deployment-evidence/mariadb-loopback-hardening/20260801T060838Z`
- Prior-state marker: `dropin-was-absent`
- Restored state: no `10-loopback-only.conf` drop-in installed

## Incident sequence

1. The final MariaDB and `res_odbc` read-only gates passed.
2. The approved socket drop-in was installed and systemd was reloaded.
3. `systemd-analyze verify mariadb.socket mariadb.service` returned nonzero only because both units reference `man:mariadbd(8)` and the manual-page check failed.
4. The operator began rollback, restored the prior absent-drop-in state, and reloaded systemd.
5. Rollback repeated the same manual-page-sensitive verification and returned before restarting MariaDB.
6. Manual recovery restarted `mariadb.socket` and `mariadb.service` under the original wildcard TCP contract.

## Verified recovery

- `mariadb.socket`: active
- `mariadb.service`: active
- TCP `3306`: restored under the original wildcard listener contract
- Unix sockets: `@mariadb` and `/run/mysqld/mysqld.sock` present
- FreePBX UCP listeners: TCP `8001` and `8003` present
- UCP Node to MariaDB relationship: fully loopback scoped
- Asterisk: zero active channels and zero active calls

A read-only host check confirmed that Edge1 systemd 252 supports:

```text
systemd-analyze verify --man=no mariadb.socket mariadb.service
```

That command completed with exit code `0` while all services remained healthy.

## Root cause

The operator treated documentation-reference validation as unit-configuration validation. Its rollback path also made static verification a prerequisite to runtime service restoration. A missing or unavailable manual page could therefore create a false deployment failure and strand MariaDB stopped after the prior unit contract had already been restored.

## Correction

The operator now:

- runs systemd unit verification with `--man=no`;
- preserves verification output in the evidence directory;
- records rollback verification status without returning early;
- always attempts to restart and verify the MariaDB socket/service pair after restoring the prior drop-in state;
- emits a rollback warning if static verification fails but runtime restoration succeeds;
- retains critical failure behavior when prior-state restoration, daemon reload, or MariaDB service restoration actually fails.

## Current decision

The baseline is restored and healthy. Loopback-only activation remains incomplete and must not be retried until the corrected operator is merged, pulled to Edge1, and repository validation passes.
