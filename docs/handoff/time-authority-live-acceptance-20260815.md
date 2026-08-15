# WW.CX Time Authority Live Acceptance — 2026-08-15

## Status

**Accepted live on `edge1.ww.cx` on 2026-08-15.**

The Time Authority deployment is operating in its intended read-only monitoring role. It does not replace or alter the host clock synchronization service, does not expose a public NTP listener, and remains bound to localhost.

## Deployed revision

- Production hardening and port-collision recovery: merge commit `8f648deb9a85605655580637a361b478291f08e1` (PR #316).
- Live-data validation isolation fix: merge commit `6a50ee4dfe9ed798d4015c3890ff52900cb598b7` (PR #317).

## Live acceptance evidence

The attended Edge1 deployment run completed successfully with the following verified state:

- production preflight passed;
- production installer completed and recorded rollback evidence under `/var/lib/wwcx-deployment-evidence/time-authority/install-20260815T191216Z`;
- `edge1-time-authority-collector.timer` is enabled and active (`waiting`), scheduled every 15 minutes;
- `edge1-time-authority-dashboard.service` is enabled and active (`running`);
- the existing `wwcx-timekeeping` service remains on `127.0.0.1:8092`;
- the Time Authority dashboard is on `127.0.0.1:8101` and reports `service: edge1-time-authority`, `read_only: true`;
- the summary API reports `mode: live` with observer `edge1` / `edge1.ww.cx`;
- all five configured NTP sources were reachable and all five expectations were met during acceptance;
- the final production smoke test passed;
- listener inspection showed separate localhost listeners on ports 8092 and 8101;
- `systemd-timesyncd.service` remained enabled and active, confirming the Time Authority deployment did not replace host clock synchronization.

## Source observations during acceptance

The live collector successfully recorded measurements from:

- Netnod Stockholm `sth1.ntp.se`, Stratum 1 / PPS;
- Netnod Stockholm `sth2.ntp.se`, Stratum 1 / PPS;
- Netnod Malmö `mmo1.ntp.se`, Stratum 1 / PPS;
- NIST `time.nist.gov`, Stratum 1 / NIST;
- Cloudflare `time.cloudflare.com`, Stratum 3 in the observed acceptance sample.

The observed values are operational measurements, not fixed service guarantees; DNS, anycast addresses, stratum, latency, and offsets may vary over time.

## Deployment incident and resolution

The first live attempt exposed a historical port collision: Time Authority was configured for localhost port 8092, which was already owned by `wwcx-timekeeping`. The dashboard therefore entered a restart loop with `OSError: [Errno 98] Address already in use`.

The production deployment was corrected by moving Time Authority to dedicated localhost port 8101, adding preflight port ownership checks, verifying health-service identity during smoke tests, explicitly restarting the dashboard after unit replacement, and preserving pre-change unit files and deployment metadata for rollback.

A second preflight issue was also discovered after the collector had written real measurements: the validation harness read the default live measurements path while asserting baseline fixture counts. PR #317 isolated that test from production data. Runtime behavior and production measurements were unchanged.

## Accepted boundary

This acceptance covers the private/read-only monitoring service only:

- localhost dashboard/API on `127.0.0.1:8101`;
- scheduled outbound NTP probes to the configured sources;
- local measurement storage and read-only API/CSV presentation;
- continued use of the existing host time synchronization service.

It does **not** approve or implement a public NTP server, UDP/123 listener, firewall rule, DNS publication, NTS service, host clock replacement, or external time-authority role.

## Result

**WW.CX Time Authority is accepted as live and operational on Edge1 within the documented read-only boundary.**
