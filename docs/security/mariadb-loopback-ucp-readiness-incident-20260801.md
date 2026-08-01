# MariaDB Loopback Hardening UCP Readiness Incident — 2026-08-01

## Scope

This record covers the corrected-rollback activation attempt at `2026-08-01T06:45:08+00:00`. It does not claim that loopback-only MariaDB hardening was activated.

## Evidence

- Host: `edge1.ww.cx`
- Evidence directory: `/var/lib/wwcx-deployment-evidence/mariadb-loopback-hardening/20260801T064508Z`
- Operator console SHA-256: `d3836d37df213fe8bce76521c8e80c99954a0f42a2ae3bc9ee43c930bed2cc89`
- Operator result: `CHANGE FAILED AND ROLLED BACK`

## Verified behavior

The corrected rollback logic restored the prior absent-drop-in state, restarted `mariadb.socket` and `mariadb.service`, and returned both units active. The original wildcard TCP 3306 listener and both Unix sockets were restored. Asterisk remained at zero active channels and calls.

## Root cause

The activation path captured TCP listeners immediately after restarting MariaDB and failed if UCP ports 8001 and 8003 were not already present. FreePBX UCP Node restarts asynchronously after its database connection is interrupted, so an immediate listener assertion can fail during a normal recovery interval.

The operator already waited for the UCP-to-MariaDB relationship, but that wait occurred only after the instantaneous UCP listener assertion. The intended readiness wait was therefore unreachable when UCP needed startup time.

## Correction

The operator now uses a bounded 60-second post-change readiness gate. Each attempt requires all of the following simultaneously:

- MariaDB TCP listeners match IPv4 and IPv6 loopback-only policy;
- both MariaDB Unix sockets are present;
- UCP listeners 8001 and 8003 are present;
- the UCP Node to MariaDB relationship is established and fully loopback scoped.

Rollback also waits for UCP listeners and its loopback database relationship after restoring and restarting the prior MariaDB contract. Failure of dependent runtime recovery remains fail-closed, but MariaDB restoration is attempted first.

## Current decision

The baseline was restored and the loopback-only drop-in is absent. No further live activation attempt is permitted until this readiness correction is merged, pulled to Edge1, and both hosted validation workflows pass.
