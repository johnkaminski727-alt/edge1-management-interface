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
sudo deploy/install-time-authority-edge1.sh
```

The installer validates the package, creates the unprivileged `bigbird-time` service account, schedules collection every 15 minutes, starts the localhost-only dashboard on port 8092, performs an immediate collection, and checks `/healthz`.

Inspect status:

```bash
systemctl status edge1-time-authority-collector.timer --no-pager
systemctl status edge1-time-authority-dashboard.service --no-pager
curl -sS http://127.0.0.1:8092/api/time-authority/summary | python3 -m json.tool
```

## Shared-host installation

Transfer or check out the package on `business159.web-hosting.com`, then run:

```bash
deploy/install-time-authority-shared-host.sh
```

The installer performs one immediate probe and prints the cPanel cron entry. It does not modify the crontab automatically. Measurements remain private under `$HOME/private/wwcx-time-authority/measurements.jsonl` until an authenticated transfer path to Edge1 is enabled.

## Big Bird integration

The dashboard is available from `src/web/time-authority/` and supports the read-only endpoint:

```text
GET /api/time-authority/summary?limit=2000
```

Place the dashboard behind the same approved private/VPN boundary as the existing management interface. Do not expose the localhost service directly to the public Internet.

To aggregate a copied shared-host JSONL file, set a colon-separated path list in the dashboard service environment:

```text
EDGE1_TIME_AUTHORITY_DATA_PATHS=/var/lib/edge1-time-authority/measurements.jsonl:/var/lib/edge1-time-authority/shared-host-measurements.jsonl
```

## Rollback

```bash
sudo systemctl disable --now edge1-time-authority-collector.timer edge1-time-authority-dashboard.service
```

Removing the units does not delete collected measurements. Keep the JSONL files for audit and spreadsheet history unless an explicit retention decision is made.
