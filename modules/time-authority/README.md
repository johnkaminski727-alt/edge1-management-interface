# WW.CX Time Authority

The Time Authority package measures NTP round-trip time and source metadata from two independent WW.CX observers:

- `edge1.ww.cx` — the Edge1/Big Bird management host;
- `business159.web-hosting.com` — the WW.CX shared-hosting observer.

It does not set either system clock. The collectors send one ordinary NTPv4 client request to each configured source, validate the response, and append normalized JSON Lines records. The read-only dashboard service aggregates those records for the Big Bird interface.

## Components

```text
config/sources.json                         source register
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
