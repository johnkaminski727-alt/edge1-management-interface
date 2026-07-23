# WW.CX mining operations dashboard

## Purpose

The dashboard presents one fleet-level traffic light and one expandable card for every miner in the registry. The browser renders a sanitized status document; it does not read miner credentials, payout addresses, or pool secrets.

## Data flow

1. Miner-specific collectors write operator-controlled telemetry JSON files.
2. `/etc/wwcx-mining/miners.json` registers miners and defines expected performance.
3. `server/mining_operations_exporter.py` evaluates every registered miner and atomically publishes `/var/www/edge1-status/mining-operations.json`.
4. `src/web/mining/index.html` refreshes that document every 60 seconds.

Adding a miner requires only a new registry object and telemetry producer. Dashboard code does not change.

## Traffic-light rules

Rules are evaluated in priority order.

- **Green:** telemetry is fresh; the miner reports online; its pool is connected; and hashrate is at or above `amber_hashrate_ratio * expected_hashrate_hs`.
- **Amber:** telemetry is older than `telemetry_fresh_seconds` but younger than `telemetry_stale_seconds`, or hashrate is below the amber ratio but not below the red ratio.
- **Red:** telemetry is invalid or stale, the miner reports offline, pool connectivity is down, or hashrate is below `red_hashrate_ratio * expected_hashrate_hs`.
- **Grey:** the miner is disabled, telemetry is absent, no hashrate expectation exists, or no active miners are registered.

The fleet status is the worst active-miner state. Disabled miners remain visible but do not degrade fleet status.

## Registry fields

Required operational fields are `id`, `name`, `telemetry_path`, `enabled`, and `expected_hashrate_hs`. Recommended fields include site, model, algorithm, freshness thresholds, hashrate ratios, pool display name, worker label, owner, location, and notes.

Keep credentials, pool URLs containing credentials, wallet addresses, API tokens, and other secrets out of the registry because its sanitized output is designed for web publication.

## Validation

Run:

```sh
python3 tests/validate_mining_operations.py
python3 -m py_compile server/mining_operations_exporter.py
```

Generate a local status document:

```sh
python3 server/mining_operations_exporter.py \
  --registry config/mining/miners.example.json \
  --output /tmp/mining-operations.json
```
