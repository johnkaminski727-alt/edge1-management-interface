# WW.CX Time Authority

The Time Authority package measures NTP round-trip time and source metadata from two independent WW.CX observers:

- `edge1.ww.cx` — the Edge1/Big Bird management host;
- `business159.web-hosting.com` — the WW.CX shared-hosting observer.

It does not set either system clock. The collectors send one ordinary NTPv4 client request to each configured source, validate the response, and append normalized JSON Lines records. The read-only dashboard service aggregates those records for the Big Bird interface.

## Components

```text
config/sources.json                         six-source live register (Netnod x3, NIST, Cloudflare, ISNIC)
config/observers.json                       observer register
fixtures/baseline-measurements.json         initial 2026-07-18 observations
tools/time_authority/ntp_rtt_probe.py        common collector
server/time_authority_server.py              read-only aggregation API
src/web/time-authority/                      responsive dashboard
deploy/systemd/edge1-time-authority-*         Edge1 services and timer
```

## Data boundary

Records contain only UTC observation time, observer identity, public NTP source identity, resolved address, NTP response metadata, RTT/offset estimates, reachability, and a bounded error class. They contain no credentials, private-library contents, or production configuration.

## Quick validation

```bash
python3 tests/validate_time_authority.py
```

See `docs/handoff/time-authority-runbook.md` for deployment and operations.

The dashboard exposes a spreadsheet-ready export at:

```text
GET /api/time-authority/export.csv?limit=5000
```

## September 2026 Edge1 rebuild

The six-source register includes `ht-time01.isnic.is`, the ISNIC GNSS-backed stratum-1 source restored on Edge1 on 2026-09-26. It is an additional upstream; existing Netnod, NIST, and Cloudflare sources remain configured. Chrony selected ISNIC without a forced `prefer` directive and Edge1 was observed operating at stratum 2.

The read-only dashboard's static `sources` metadata reads this tracked register; the RTT collector defaults to the same file. Previously installed Edge1 systems may have a local `EDGE1_TIME_AUTHORITY_SOURCES=/etc/edge1-time-authority/sources.json` systemd override. Check that both catalogs contain the same six source IDs after deployment. Historic baseline fixtures deliberately remain at their original five-source snapshot.

Operational acceptance on 2026-09-26: collector and dashboard reported 6/6 reachable and 6/6 expectations met; Windows Wi-Fi externally verified TCP/4460, the `ntp.ww.cx` TLS certificate, TLS 1.3 and ALPN `ntske/1`, and received 3/3 standard UDP/123 NTP replies. A full authenticated NTS time exchange and Business159's outbound TCP/4460 restriction remain separate acceptance items. The Certbot renew dry run with `--run-deploy-hooks` succeeded and restarted Chrony with local NTS and standard NTP passing.
