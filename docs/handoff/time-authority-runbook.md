# WW.CX Time Authority Runbook

## Purpose

The package records time-source reachability and performance from `edge1.ww.cx` and `business159.web-hosting.com`. It is deliberately read-only: it does not alter either system clock and does not yet replace Edge1's active `systemd-timesyncd` service.

## Registered sources

| Source ID | Server name | Baseline IPv4 | Provider | Expected response |
| --- | --- | --- | --- | --- |
| `netnod-sth1` | `sth1.ntp.se` | `194.58.202.20` | Netnod | Stratum 1 / PPS |
| `netnod-sth2` | `sth2.ntp.se` | `194.58.202.148` | Netnod | Stratum 1 / PPS |
| `netnod-mmo1` | `mmo1.ntp.se` | `194.58.204.20` | Netnod | Stratum 1 / PPS |
| `nist-global` | `time.nist.gov` | dynamic (`132.163.97.1` and `.4` observed) | NIST | Stratum 1 / NIST |
| `cloudflare-global` | `time.cloudflare.com` | `162.159.200.123` | Cloudflare | Stratum 1–4 |

DNS remains authoritative. Addresses are recorded per measurement because anycast and load-balanced services may change them.

## Edge1 installation

From `/opt/edge1-management-interface`:

```bash
deploy/time-authority-edge1-preflight.sh
sudo deploy/install-time-authority-edge1.sh
```

The installer validates the package, verifies that the dashboard port is either free or already owned by Time Authority, creates the unprivileged `bigbird-time` service account when needed, schedules collection every 15 minutes, starts the localhost-only dashboard on port 8101, performs an immediate collection, and runs the production smoke test.

Port `8092` is not available for Time Authority on the current Edge1 host: a live deployment check on 2026-08-15 identified `wwcx-timekeeping` there. Time Authority therefore uses the dedicated localhost port `8101`. Do not move either service merely to make the other fit; change the Time Authority port only through a reviewed deployment update and preflight it first.

Inspect status:

```bash
systemctl status edge1-time-authority-collector.timer --no-pager
systemctl status edge1-time-authority-dashboard.service --no-pager
curl -sS http://127.0.0.1:8101/healthz | python3 -m json.tool
curl -sS http://127.0.0.1:8101/api/time-authority/summary | python3 -m json.tool
sudo deploy/time-authority-edge1-smoke-test.sh
```

The expected health identity is `service: edge1-time-authority` with `read_only: true`. A successful response from a different service is a port collision, not a successful Time Authority deployment.

## Shared-host installation

Transfer or check out the package on `business159.web-hosting.com`, then run:

```bash
deploy/install-time-authority-shared-host.sh
```

The installer requires Python 3.6 or newer, performs one immediate probe, installs the 15-minute user crontab entry idempotently, and runs a shared-host smoke test. Set `WWCX_TIME_AUTHORITY_PYTHON` when cPanel provides the desired interpreter under a non-default path. Set `WWCX_TIME_AUTHORITY_INSTALL_CRON=0` only when cPanel will manage the schedule separately. Measurements remain private under `$HOME/private/wwcx-time-authority/measurements.jsonl` until an authenticated transfer path to Edge1 is enabled.

## Big Bird integration

The dashboard is available from `src/web/time-authority/` and supports the read-only endpoint:

```text
GET /api/time-authority/summary?limit=2000
GET /api/time-authority/export.csv?limit=5000
```

The CSV export uses the same columns as the companion RTT tracking workbook and can be imported or appended without reshaping the measurement data.

## Offline rollout simulation

Before an operator shell is available, exercise both installers end to end without touching host services:

```bash
python3 tests/validate_time_authority_rollout_simulation.py
```

The simulator uses temporary data and unit directories, a fake `systemctl`/crontab layer, a local NTP responder, and the real dashboard HTTP/CSV paths. Edge1 simulation mode refuses to run with either the production unit directory or the real `systemctl` command.

Place the dashboard behind the same approved private/VPN boundary as the existing management interface. Do not expose the localhost service directly to the public Internet.

To aggregate a copied shared-host JSONL file, set a colon-separated path list in the dashboard service environment:

```text
EDGE1_TIME_AUTHORITY_DATA_PATHS=/var/lib/edge1-time-authority/measurements.jsonl:/var/lib/edge1-time-authority/shared-host-measurements.jsonl
```

## Rollback

```bash
sudo systemctl disable --now edge1-time-authority-collector.timer edge1-time-authority-dashboard.service
```

Production installation preserves pre-existing Time Authority unit files and install metadata under `/var/lib/wwcx-deployment-evidence/time-authority/install-<UTC timestamp>/` before unit replacement. Review that evidence before restoring an earlier unit definition.

On shared hosting, remove only the exact managed cron line:

```bash
crontab -l | grep -Fv "$HOME/wwcx-time-authority/collect-shared-host.sh" | crontab -
```

Removing the units does not delete collected measurements. Keep the JSONL files for audit and spreadsheet history unless an explicit retention decision is made.
