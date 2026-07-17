# Spamhaus Filtering Runbook

This runbook installs and verifies the Edge1 Spamhaus network filter.

The filter uses Spamhaus DROP, EDROP, and DROPv6 when available. EDROP has been
merged into DROP by Spamhaus, so an empty EDROP count is acceptable. The filter
owns only the `inet bigbird_spamhaus` nftables table and does not modify
existing firewall tables or default policies.

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

## Verify

```bash
cd /opt/edge1-management-interface
sudo tools/networking/spamhaus-filter-smoke-test.sh
```

Expected evidence:

- `nft list table inet bigbird_spamhaus` succeeds.
- `drop4` and `combined4` counts are non-zero.
- `bigbird-spamhaus-filter.service` exits successfully.
- `bigbird-spamhaus-filter.timer` is enabled and scheduled.

## Manual Refresh

```bash
sudo systemctl start bigbird-spamhaus-filter.service
sudo cat /var/lib/bigbird-networking/spamhaus/summary.txt
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

## Notes

- The table uses `policy accept`; it only drops source addresses in the
  Spamhaus sets.
- Rules are applied only after the generated nftables file passes `nft -c`.
- The refresh interval is six hours with a randomized delay to avoid fixed
  polling spikes.
