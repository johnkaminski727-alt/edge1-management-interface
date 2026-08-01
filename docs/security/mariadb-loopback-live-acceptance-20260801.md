# MariaDB Loopback Hardening Live Acceptance — 2026-08-01

## Result

The approved loopback-only MariaDB socket contract was applied successfully on `edge1.ww.cx` at `2026-08-01T07:09:57+00:00`.

## Evidence

- Evidence directory: `/var/lib/wwcx-deployment-evidence/mariadb-loopback-hardening/20260801T070803Z`
- Operator console SHA-256: `2ed603b22e79fd4610af5aafac2d60906e5b149188c6b7dac5f6327a7231d25f`
- Installed drop-in SHA-256: `c5365e2d9bd882fcf62a8676b98f8f996094c5b5e45572fe9a0244b7f4f32fea`
- Readiness completed on attempt: `4` of `60`
- Operator result: `CHANGE APPLIED AND VERIFIED`

## Accepted runtime state

- `mariadb.socket` and `mariadb.service` were active and running.
- TCP 3306 listened only on `127.0.0.1` and `::1`.
- The abstract `@mariadb` socket and `/run/mysqld/mysqld.sock` remained present.
- FreePBX UCP listeners 8001 and 8003 recovered.
- One UCP Node client relationship and the matching MariaDB server relationship were established entirely over IPv4 loopback.
- Asterisk reported zero active channels and zero active calls.
- The installed drop-in metadata was `0644 root:root`, and its hash matched the approved source.

## Non-impact statement

No call was originated. No emergency calling, live carrier routing, firewall, WireGuard, database schema, grant, package, CAP feed, or external traffic change was performed by this activation.

## Warning cleanup

The successful run emitted a GNU `awk` warning because the UCP client regular expression unnecessarily escaped a double quote. The match and acceptance result were correct. The operator source was subsequently corrected to remove that warning, with a regression assertion preventing its return.
