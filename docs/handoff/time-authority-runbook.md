# WW.CX Time Authority Runbook

## Purpose

The read-only dashboard and collectors record time-source reachability and performance from `edge1.ww.cx` and `business159.web-hosting.com`. Separately, Edge1 operates a public Chrony NTP server with NTS-KE. On the rebuilt Debian 13 host as of 2026-09-26, Chrony replaced `systemd-timesyncd` and synchronized to the ISNIC stratum-1 network upstream, making Edge1 a stratum-2 server. The collectors do not set the clock; Chrony does.

## Registered sources

| Source ID | Server name | Baseline IPv4 | Provider | Expected response |
| --- | --- | --- | --- | --- |
| `netnod-sth1` | `sth1.ntp.se` | `194.58.202.20` | Netnod | Stratum 1 / PPS |
| `netnod-sth2` | `sth2.ntp.se` | `194.58.202.148` | Netnod | Stratum 1 / PPS |
| `netnod-mmo1` | `mmo1.ntp.se` | `194.58.204.20` | Netnod | Stratum 1 / PPS |
| `nist-global` | `time.nist.gov` | dynamic (`132.163.97.1` and `.4` observed) | NIST | Stratum 1 / NIST |
| `cloudflare-global` | `time.cloudflare.com` | `162.159.200.123` | Cloudflare | Stratum 1–4 |
| `isnic-ht-time01` | `ht-time01.isnic.is` | `193.4.58.77` (observed) | ISNIC | GNSS-backed stratum 1 |

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

## September 26, 2026 rebuild: authoritative operating notes

The rebuilt Edge1 public IPv4 is `89.126.248.191` (retired address `89.147.109.253`). Both `ntp.ww.cx` and `time.ww.cx` resolved to the new IPv4 after cutover. The external Windows Wi-Fi network verified TCP/4460, the Let's Encrypt certificate for `ntp.ww.cx`, TLS 1.3 with `ntske/1`, and three standard UDP/123 NTP responses. Business159 could query UDP/123 but its TCP/4460 attempts were refused; Windows' independent Wi-Fi connection succeeded. Do **not** classify the Business159 refusal as a global outage or change Edge1 firewall rules without packet evidence.

**Service and security layout**:

- `chrony.service`: public NTP UDP/123 and NTS-KE TCP/4460; certificate staged under `/etc/chrony/nts/`, owned by `root:_chrony` with mode 0640.
- Dedicated Certbot lineage `/etc/letsencrypt/live/ntp.ww.cx/` issued using the standalone HTTP-01 authenticator. The ECDSA certificate issued 2026-09-26 expires 2026-12-25 UTC. `certbot.timer` is enabled; the guarded deploy hook is `/etc/letsencrypt/renewal-hooks/deploy/50-wwcx-ntp-chrony-nts`.
- UFW is the active Edge1 firewall, backed by iptables-nft. The public inbound IPv4 rules on `ens3` scope TCP/80 (standalone ACME validation), UDP/123, and TCP/4460 to `89.126.248.191`. Preserve SSH and WireGuard rules. `nftables.service` is disabled and the previous bespoke `inet wwcxfw` ruleset does not exist. **Do not run old nftables firewall publisher or Apache-dependent certificate scripts on the rebuilt host** without a new implementation and review.
- Dashboard stays private on `127.0.0.1:8101`, with the RTT collector scheduled every 15 minutes by `edge1-time-authority-collector.timer`. Chrony's six upstreams are Netnod ×3, NIST, Cloudflare, and ISNIC `ht-time01.isnic.is`. Preserve `minsources 3` and do not force ISNIC with `prefer`.

**Certificate lifecycle acceptance already completed**: `sudo certbot renew --dry-run --run-deploy-hooks --cert-name ntp.ww.cx` succeeded. The hook staged the existing live certificate, restarted Chrony, waited for synchronization, and verified local NTP and local NTS TLS. The evidence directory is `/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-renewal-20260926T173856Z`. A plain dry run without `--run-deploy-hooks` does **not** test the deployment hook.

**ISNIC acceptance already completed**: guarded installer `deploy/install-time-authority-isnic-upstream-edge1.sh` installed `/etc/chrony/conf.d/wwcx-isnic-upstream.conf` and preserved the other upstreams. It verified a synchronized stratum-1 ISNIC preflight, standard NTP, NTS listener and TLS `ntske/1`, and observed Edge1 at stratum 2. Evidence: `/var/lib/wwcx-deployment-evidence/public-ntp-server/isnic-upstream-20260926T174018Z`.

**Collector catalog**: the six-source tracked register in `modules/time-authority/config/sources.json` is the default collector register and the dashboard's static `sources` metadata. The original historical baseline fixtures remain five-source snapshots. During rebuilding, a temporary systemd override was set for `edge1-time-authority-collector.service` at `/etc/systemd/system/edge1-time-authority-collector.service.d/20-six-sources.conf` to read `/etc/edge1-time-authority/sources.json`. On deployment, check both catalogs contain exactly the same six source IDs; remove the override only through a reviewed change. The live dashboard API confirmed six of six reachable and six of six expectations met at 17:42 UTC on 2026-09-26.

**Outstanding acceptance**: verify a *full authenticated NTS time exchange* from an independent external NTS client, not just TLS/ALPN; resolve Business159's path-specific TCP/4460 refusal; reconcile its shared-host monitoring and status publication; separately investigate Windows WireGuard route-to-public-IP behavior if still reproducible. Do not alter production Chrony, UFW, DNS, or certificate state merely to satisfy the final documentation review.

**Non-destructive read-only checks (run on Edge1)**:

```bash
sudo chronyc tracking
sudo chronyc sources -v
sudo ss -ltnup | grep -E ':(123|4460)\\b'
sudo ufw status numbered
systemctl is-active chrony.service edge1-time-authority-collector.timer edge1-time-authority-dashboard.service
curl -fsS http://127.0.0.1:8101/healthz
curl -fsS 'http://127.0.0.1:8101/api/time-authority/summary?limit=200' | python3 -m json.tool
systemctl list-timers certbot.timer --no-pager
```

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
