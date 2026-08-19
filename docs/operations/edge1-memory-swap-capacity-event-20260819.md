# Edge1 memory and swap capacity event — 2026-08-19

## Summary

A private WW.CX Messaging Gateway staging/acceptance session exposed a host-capacity problem on Edge1. The Messaging deployment did not cause the underlying memory pressure; the issue was discovered by the post-deployment resource gate while validating the isolated Messaging runtime.

At discovery time Edge1 had approximately 3.8 GiB RAM, about 1.4 GiB `MemAvailable`, and the original 1 GiB `/swapfile` was effectively full. Live `vmstat` and PSI sampling later confirmed that the host was not merely carrying stale swap: after the regular scheduled reboot and service initialization, the machine showed sustained swap-out, non-trivial full-memory pressure, and significant I/O wait.

The largest memory consumers were the passive Suricata sensor on `wg0` and Bitcoin Core. Suricata initially accounted for roughly 598 MiB resident plus 737 MiB swapped; Bitcoin Core accounted for roughly 1 GiB resident with additional swap use.

## Trigger and scope

The condition was discovered while completing private Messaging Phase 3 live acceptance. The Messaging Gateway itself remained healthy and private:

- loopback-only listener on `127.0.0.1:58080`;
- PostgreSQL socket-only storage;
- simulator-only provider registry;
- outbound and inbound workers disabled;
- no carrier credentials, DIDs, billing, public webhook, DNS/firewall/TLS/authentication change, production telephony routing, or live SMS/MMS traffic.

The capacity investigation interrupted the remaining Phase 3 live acceptance work after the private runtime had been deployed through commit `3fec8df207587fc794a4751f4584fc1162b360da` (PR #437-era state).

## Investigation

Read-only inspection showed:

- `vm.swappiness=60` and `vm.vfs_cache_pressure=100`;
- no OOM-killer events in the sampled period;
- the first live swap samples were quiet, but Suricata owned the majority of swap;
- Suricata was confirmed to be `wwcx-network-sensor-suricata.service`, a passive IDS using `--pcap=wg0`, not an inline NFQueue forwarding component;
- a controlled restart of only that passive sensor reclaimed roughly 715 MiB of stale Suricata swap initially;
- after service initialization and the normal 12-hour Edge1 reboot cycle, Suricata returned to six threads and approximately 1.3 GiB combined RSS+swap while Bitcoin Core also remained memory-heavy;
- a 60-second steady-state sample then showed sustained swap-in/swap-out and material PSI full-memory stalls, confirming a real capacity constraint rather than only stale swap accounting.

The exact 12-hour reboot cadence was separately traced to the intentional temporary cron program `/etc/cron.d/edge1-auto-reboot`, which invokes `/usr/local/sbin/edge1-scheduled-reboot` at 00:40 and 12:40 UTC and is configured to expire 2027-02-07. This reboot program is known and intentional and was not treated as an incident cause.

## Remediation

The original `/swapfile` was preserved unchanged at priority `-2`.

A second 2 GiB swapfile was added at `/swapfile2` with:

- owner `root:root`;
- mode `0600`;
- swap priority `-3`;
- persistent `/etc/fstab` entry: `/swapfile2 none swap sw,pri=-3 0 0`.

This increased total swap capacity from approximately 1 GiB to 3 GiB while retaining the original swapfile as the higher-priority area. `/etc/fstab` was backed up under `/var/backups/edge1-swap/20260819T004554Z/`, and `systemctl daemon-reload` was run after the persistent entry was added.

Post-change verification showed approximately 3 GiB total swap with roughly 2.4 GiB free at the time of verification. No VM tuning values were changed and no broad service restart was performed as part of the swap-capacity remediation.

## Operational conclusions

1. The original 1 GiB swap allocation was too small for the current Edge1 workload envelope.
2. Suricata and Bitcoin Core together dominate RAM/swap pressure; the Messaging Gateway is not a primary memory consumer.
3. Additional swap provides failure-margin and reduces immediate OOM risk, but does not replace future workload/memory tuning.
4. Do not use `swapoff -a` on this host without a fresh capacity check; forcing all swapped pages resident could create avoidable OOM pressure.
5. Keep `vm.swappiness=60` unchanged until a longer steady-state observation demonstrates a reason to tune global VM policy.
6. Future deployment acceptance on Edge1 should include pre- and post-change `MemAvailable`, swap utilization, PSI memory pressure, and short live `vmstat` sampling before declaring the host healthy for additional load.

## Messaging continuation point

The repository subsequently advanced to `dc103f013ca6e95f1b10a16070591f6d8f93c889` through PR #440, incorporating the remaining Phase 3 review fixes including delivery-status reconciliation, webhook collision/audit handling, and repository/live readiness reconciliation.

The next uncompleted task is therefore to bring the isolated live Messaging runtime from the deployed PR #437-era target to the final Phase 3 repository state, then perform bounded simulator/local acceptance and capture live evidence. Carrier/public activation remains explicitly out of scope.
