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

The existing `edge1-snmp-poller.timer` remains the schedule authority and runs every five minutes. No additional daemon or timer is required.

The same command also checks this optional import location:

```text
/var/lib/edge1-snmp/server-pollers/business159-measurements.jsonl
```

Absence is a normal state. Do not populate that path through an unauthenticated or public transfer mechanism.

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

This mirrors the accepted Time Authority shared-host pattern. Measurements remain private on the shared host until an authenticated transfer path to Edge1 is explicitly enabled.

## Central import

Once an authenticated copy path exists, copy the shared-host JSONL to:

```text
/var/lib/edge1-snmp/server-pollers/business159-measurements.jsonl
```

The Edge1 poller cycle imports records idempotently. A unique key on poller/timestamp/metric/source prevents duplicate metrics when the same copied file is seen repeatedly.

Do not make the JSONL file public merely to simplify transport.

## Validation

Repository validation:

```bash
python3 tests/validate_snmp_server_pollers.py
```

Live Edge1 checks after deployment should confirm:

- `edge1-snmp-poller.service` succeeds;
- the `edge1` row exists in `server_pollers`;
- recent `server_metrics` samples exist;
- the SNMP `devices` count is still the genuine SNMP inventory count;
- no UDP 161/162 listeners appeared;
- existing SNMP API and BigBird listeners remain loopback-only.

Shared-host checks should confirm the managed cron line exists once, the private JSONL file is mode `0600`, and a fresh record has schema `wwcx.snmp-server-poller.v1`.

## Acceptance semantics

Host-native server pollers are operational telemetry sources, not SNMPv3 endpoints. PR #413 must remain draft until a legitimate authorized SNMPv3 `authPriv` endpoint/profile is tested successfully, unless the project acceptance policy is explicitly changed later.
