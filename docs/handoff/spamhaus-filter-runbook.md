# Spamhaus Filtering Runbook

This runbook installs, verifies, reports, and rolls back the Edge1 Spamhaus
network filter.

The filter uses Spamhaus DROP, EDROP, and DROPv6 when available. EDROP has been
merged into DROP by Spamhaus, so an empty EDROP count is acceptable. The filter
owns only the `inet bigbird_spamhaus` nftables table and does not modify
existing firewall tables or default policies.

## Current Verified State

Verified on 2026-07-17:

| Check | Value |
| --- | --- |
| nftables table | `inet bigbird_spamhaus` |
| DROP IPv4 networks | `1576` |
| EDROP IPv4 networks | `0` |
| Combined IPv4 networks | `1576` |
| DROP IPv6 networks | `87` |
| systemd service result | `success` |
| systemd timer | `active` |
| ww.cx status endpoint | `state: ok` |

The service is `Type=oneshot`, so `inactive (dead)` after a successful run is
normal. Use `systemctl show -p Result --value bigbird-spamhaus-filter.service`
for the most recent execution result.

## Install

```bash
cd /opt/edge1-management-interface
sudo tools/networking/install-spamhaus-filter.sh
```

The installer copies the updater to:

```text
/usr/local/sbin/bigbird-spamhaus-nft-update
```

It also installs and starts:

```text
/etc/systemd/system/bigbird-spamhaus-filter.service
/etc/systemd/system/bigbird-spamhaus-filter.timer
```

## Verify Live Filter

```bash
cd /opt/edge1-management-interface
sudo tools/networking/spamhaus-filter-smoke-test.sh
```

Expected evidence:

- `nft list table inet bigbird_spamhaus` succeeds.
- `drop4` and `combined4` counts are non-zero.
- `bigbird-spamhaus-filter.service` exits with `status=0/SUCCESS`.
- `bigbird-spamhaus-filter.timer` is active and scheduled.

## Manual Refresh

```bash
sudo systemctl start bigbird-spamhaus-filter.service
sudo cat /var/lib/bigbird-networking/spamhaus/summary.txt
```

## Push Status to ww.cx

Retrieve the network-manager token from the private shared-host config on
`business159`, then run the push from Edge1:

```bash
cd /opt/edge1-management-interface
bash tools/networking/push-spamhaus-status.sh
```

Expected readback:

```text
state: ok
drop4_count: 1576
combined4_count: 1576
drop6_count: 87
service_state: success
timer_state: active
```

## Rollback

This removes only the Big Bird Spamhaus filter and timer.

```bash
sudo systemctl disable --now bigbird-spamhaus-filter.timer
sudo rm -f /etc/systemd/system/bigbird-spamhaus-filter.service
sudo rm -f /etc/systemd/system/bigbird-spamhaus-filter.timer
sudo systemctl daemon-reload
sudo nft delete table inet bigbird_spamhaus
```

## Security Follow-Up

Rotate these values after handoff because they were used during setup:

- The `wwcxjywl_nm` MySQL user password on `business159`.
- The network-manager bearer token in
  `/home/wwcxjywl/private/network-manager-spamhaus.php`.

After rotation, rerun the shared-host config update and
`tools/networking/push-spamhaus-status.sh`.

## Notes

- The table uses `policy accept`; it only drops source addresses in the
  Spamhaus sets.
- Rules are applied only after the generated nftables file passes `nft -c`.
- The updater collapses overlapping CIDR ranges before generating nftables
  interval sets.
- The refresh interval is six hours with a randomized delay to avoid fixed
  polling spikes.
