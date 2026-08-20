# SNMP Operations host-native server pollers

## Purpose

Server pollers provide useful host telemetry for the WW.CX SNMP Operations workstream before genuine SNMPv3 `authPriv` devices are available. They are deliberately **not** SNMP devices and do not satisfy the real-device SNMPv3 acceptance gate.

The first two poller identities are:

- `edge1` — `edge1.ww.cx`, collected locally by the existing Edge1 five-minute SNMP poller timer;
- `business159-shared-host` — `business159.web-hosting.com`, collected under the cPanel account by a user-level five-minute cron.

## Security boundary

The collector is host-native and read-only. It does not:

- start `snmpd` or `snmptrapd`;
- bind UDP 161/162 or any new network listener;
- create SNMP credential profiles;
- downgrade to SNMPv1/v2c;
- collect passwords, credential values, private keys, process command lines, service names, interface addresses, or packet data;
- make outbound network requests.

Collected metrics are limited to CPU count, load averages, uptime, memory totals/availability/utilization, filesystem totals/free/utilization for one configured path, and process count.

Edge1 stores server telemetry in dedicated `server_pollers` and `server_metrics` tables inside the existing SNMP SQLite database. The real SNMP `devices` table remains unchanged.

## Edge1 collection

`edge1-snmp-poller.service` continues to run the ordinary SNMP cycle first. It then runs:

```text
edge1_snmp_server_pollers.py poll-local \
  --poller-id edge1 \
  --display-name "Edge1 Server" \
  --observer-host edge1.ww.cx \
  --disk-path /
```

The existing `edge1-snmp-poller.timer` remains the schedule authority and runs every five minutes. No additional poller timer is required.

The same command imports the authenticated Business159 copy from:

```text
/var/lib/edge1-snmp/server-pollers/business159-measurements.jsonl
```

Absence remains a normal state. The path must never be populated through an unauthenticated or public transfer mechanism.

## Shared-host collection

On `business159.web-hosting.com`, run:

```bash
deploy/install-snmp-server-poller-shared-host.sh
```

The installer:

1. requires Python 3.6 or newer;
2. installs the portable collector under `$HOME/wwcx-snmp-server-poller/`;
3. creates one immediate sample;
4. stores measurements as mode `0600` JSONL at `$HOME/private/wwcx-snmp-server-poller/measurements.jsonl`;
5. installs one idempotent five-minute user crontab line;
6. validates the resulting schema and secret-free field set.

This mirrors the accepted Time Authority shared-host pattern.

## Authenticated Business159 -> Edge1 sync

`edge1-snmp-business159-sync.service` is a short root-only oneshot used as a dependency of the normal Edge1 poller cycle. It does **not** introduce a new timer or network listener.

The sync calls the existing reviewed strict SSH wrapper:

```text
/usr/local/libexec/business159-tunnel/ssh
```

That wrapper uses the isolated Business159 operator SSH configuration and known-hosts database. The SNMP sync does not contain or copy an SSH key, password, token, community string, or other credential.

Each sync:

1. connects non-interactively with `BatchMode=yes` and strict host-key verification;
2. reads only the private Business159 measurements path;
3. transfers at most the most recent 576 records (48 hours at five-minute cadence);
4. limits the copied payload to 2 MiB;
5. validates every JSONL record with the existing `edge1_snmp_server_pollers.validate_snapshot()` validator;
6. additionally requires exact poller id `business159-shared-host`, exact observer host `business159.web-hosting.com`, and source type `host-native`;
7. rejects secret-like markers before acceptance;
8. atomically replaces the Edge1 import file only after validation succeeds;
9. leaves the previous known-good import file untouched when fetch or validation fails.

The service runs with systemd hardening, no capabilities, a strict writable path limited to `/var/lib/edge1-snmp/server-pollers`, and no access grant from `wwadmin` to Business159 SSH material.

`edge1-snmp-poller.service` declares the sync as `Wants=` plus `After=`. Therefore every ordinary five-minute SNMP poller start attempts a fresh authenticated sync first, but a Business159 outage does not prevent local Edge1/SNMP polling from proceeding with the last known-good copied data.

## Central import

After a successful sync, the normal Edge1 poller cycle imports:

```text
/var/lib/edge1-snmp/server-pollers/business159-measurements.jsonl
```

Records are imported idempotently. A unique key on poller/timestamp/metric/source prevents duplicate metrics when the same copied file is seen repeatedly.

Do not make the JSONL file public merely to simplify transport.

## Validation

Repository validation:

```bash
python3 tests/validate_snmp_server_pollers.py
```

Live Edge1 checks after deployment should confirm:

- `edge1-snmp-business159-sync.service` succeeds and exits;
- the copied file is owned by `wwadmin:wwadmin`, mode `0600`;
- `edge1-snmp-poller.service` succeeds after the sync;
- both `edge1` and `business159-shared-host` rows exist in `server_pollers`;
- recent `server_metrics` samples exist for both pollers;
- the SNMP `devices` count is still the genuine SNMP inventory count;
- no UDP 161/162 listeners appeared;
- existing SNMP API and BigBird listeners remain loopback-only.

Shared-host checks should confirm the managed cron line exists once, the private JSONL file is mode `0600`, and a fresh record has schema `wwcx.snmp-server-poller.v1`.

## Acceptance semantics

Host-native server pollers are operational telemetry sources, not SNMPv3 endpoints. PR #413 must remain draft until a legitimate authorized SNMPv3 `authPriv` endpoint/profile is tested successfully, unless the project acceptance policy is explicitly changed later.
