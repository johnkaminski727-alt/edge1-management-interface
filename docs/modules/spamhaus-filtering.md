# Spamhaus and Network Reputation Filtering Module

## Purpose

The Spamhaus filtering module maintains a dedicated nftables table on Edge1 from the Spamhaus DROP, EDROP, and DROPv6 feeds. It blocks listed source networks in the input and forward paths without changing unrelated firewall tables or their default policies.

## Components

- `tools/networking/spamhaus-nft-update.sh` downloads, validates, normalizes, and applies the feeds.
- `tools/networking/install-spamhaus-filter.sh` installs the updater and systemd units.
- `tools/networking/spamhaus-filter-smoke-test.sh` validates the installed table, saved state, service result, and timer.
- `tools/networking/systemd/bigbird-spamhaus-filter.service` runs one refresh.
- `tools/networking/systemd/bigbird-spamhaus-filter.timer` schedules recurring refreshes.
- `tools/networking/push-spamhaus-status.sh` publishes sanitized status to the WW.CX network-management surface when configured.

## Safety model

The module owns only `inet bigbird_spamhaus`. Generated rules are syntax-checked with `nft -c` before application. Feed entries are parsed as IP networks, private and special-use ranges are rejected, duplicate and overlapping IPv4 ranges are collapsed, and an empty primary DROP feed aborts the update.

When refreshing an existing installation, the updater deletes and recreates its dedicated table in one nftables ruleset. It does not flush or alter unrelated tables.

## Installation

```bash
cd /opt/edge1-management-interface
sudo tools/networking/install-spamhaus-filter.sh
```

## Verification

```bash
sudo tools/networking/spamhaus-filter-smoke-test.sh
```

A successful oneshot service is normally `inactive (dead)` after execution. The decisive values are `Result=success`, `ExecMainStatus=0`, an active timer, and non-zero `combined4` in the saved summary.

## Verified production repair

On 2026-07-21, Edge1 was repaired after repeated `File exists` failures while recreating nftables sets. The repository implementation now:

1. collapses the combined DROP and EDROP IPv4 address space; and
2. deletes and recreates the module-owned table instead of flushing and then redefining existing sets.

The repaired service completed successfully with 1,567 combined IPv4 networks and 87 IPv6 networks. These counts are operational evidence, not fixed acceptance thresholds, because upstream feed contents change.

## Related filtering

This module is the network-prefix reputation layer. DNSBL query integration, mail-content filtering, application-level abuse scoring, allowlists, exception workflows, and other reputation providers should be implemented as separate modules that can consume a shared filtering-status interface without weakening this nftables boundary.

## Rollback

Follow `docs/handoff/spamhaus-filter-runbook.md`. Rollback removes only the module timer, service, updater, and `inet bigbird_spamhaus` table.
