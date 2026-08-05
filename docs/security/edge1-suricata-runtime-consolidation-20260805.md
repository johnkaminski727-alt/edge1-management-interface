# Edge1 Suricata runtime consolidation

## Verified live condition

On 2026-08-05, Edge1 had two enabled Suricata runtimes on `wg0`:

- `suricata.service`, described as Project Big Bird Suricata IDS on WireGuard, using forced AF_PACKET;
- `wwcx-network-sensor-suricata.service`, using explicit libpcap capture selected by the guarded network-sensor deployment.

The legacy AF_PACKET runtime had been OOM-killed and restarted, consumed approximately 1.2 GiB after restart, and remained blind on the WireGuard RAW interface. The managed sensor passed live capture acceptance with nonzero counters and zero kernel drops.

## Consolidated ownership

The managed network-sensor runtime becomes the sole packet inspection process:

- service: `wwcx-network-sensor-suricata.service`;
- EVE source: `/var/log/wwcx-network-sensor/suricata/eve.json`;
- capture backend on explicitly authorized addressed interfaces: libpcap;
- full PCAP recorder: `wwcx-network-sensor-pcap.service`.

Project Big Bird keeps its existing normalized alert schema and collector release contract, but its collector now reads the managed EVE source and reports the managed service identity. Raw events, packet payloads, credentials, and private keys remain excluded from the operations snapshot.

## Reload contract

Suricata uses `SIGUSR2` for a live rule reload. `SIGHUP` only closes and reopens log files. The managed unit therefore defines:

```ini
ExecReload=+/bin/kill -USR2 $MAINPID
```

The `+` prefix keeps the narrowly scoped packet-capture capability boundary unchanged while allowing only the systemd reload control command to signal the daemon after Suricata drops to its service account. The consolidation transaction installs and verifies this contract but does not execute a live rule reload. Reloading rules is an independent administrative action because Suricata temporarily needs memory for both detection engines during a reload.

## Guarded migration

Run only from a clean `main` checkout on Edge1 after the reviewed commit is merged:

```bash
cd /opt/edge1-management-interface
git switch main
git pull --ff-only origin main
EXPECTED_COMMIT=<full-merged-commit-sha> \
  sudo -E bash deploy/consolidate-edge1-suricata-runtime.sh
```

The migration:

1. verifies the managed sensor is enabled, active, and has a passing nonzero capture-acceptance record;
2. validates the collector against the managed EVE source and validates the reviewed unit contains privileged `SIGUSR2` rule-reload support;
3. records the initial enabled and active state of both Suricata units;
4. backs up the live Project Big Bird collector and the live managed sensor unit;
5. installs the reviewed collector and managed unit, runs `systemctl daemon-reload`, and confirms the loaded unit exposes the expected reload contract;
6. publishes the updated collector before stopping anything and confirms Security Operations, Security Correlation, and Network Defense accept the managed source;
7. disables and stops only `suricata.service`;
8. verifies exactly one Suricata main process remains, that it uses `--pcap=`, and that the managed service remains active;
9. republishes the observability pipeline and records protected evidence.

The migration deliberately does not reload or restart the managed sensor. Any failure after mutation captures the failing service state and journal before restoration, restores the previous collector and managed unit, restores the managed sensor's prior enablement and active state, and restores the exact enabled and active state of `suricata.service`.

## Boundaries

The consolidation does not change WireGuard, routes, NAT, nftables, DNS, listeners, IDS rules, PCAP retention, or traffic controls. The legacy unit file and historical `/var/log/suricata` data are retained; only the unit's enabled and active state changes.

## Follow-up

Metadata rotation for `/var/log/wwcx-network-sensor/suricata` should be reviewed separately against the intended 90-day metadata policy. That retention change is not bundled into the runtime consolidation.
