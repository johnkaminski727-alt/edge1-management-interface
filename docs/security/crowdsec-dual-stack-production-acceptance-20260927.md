# Edge1 CrowdSec dual-stack production acceptance — 2026-09-27

**Status:** Production input-path protection operational and post-reboot accepted based on operator-supplied console verification (Assignment 133). **Classification:** Sanitized public engineering record; detailed recovery evidence belongs in the private operations library.

## Architecture

- UFW remains Edge1's primary IPv4/IPv6 firewall, using the iptables-nft backend; CrowdSec uses independent, Edge1-owned nftables tables.
- An enabled, idempotent bootstrap service prepares both blacklist sets and separate, initially unhooked management guard chains after UFW and WireGuard start.
- A second enabled service attaches two CrowdSec input hooks at priority -10, each jumping to the respective guard chain. The guard chains exempt the approved WireGuard management interface and listener before checking the blacklist.
- The CrowdSec bouncer requires and starts after the enforcement service. Both families use the effective local nftables configuration with `set-only: true`; the bouncer manages blacklist membership, not the hook chains.
- The acceptance scope is **traffic destined for Edge1**. This section describes the earlier INPUT-only milestone. A later, separately accepted [IPv4 VPN FORWARD deployment](crowdsec-vpn-forward-production-acceptance-20260927.md) passed live packet-drop and production reboot testing. IPv6 VPN forwarding remains disabled.

## Verified milestones

| Test | Observed result |
|---|---|
| Existing and absent bootstrap tables | Idempotence and recreation passed |
| Ordinary UFW reload with staged guards | CrowdSec tables preserved; UFW, WireGuard and DNS stayed active |
| Bootstrap reboot | Startup and isolated guard restoration passed |
| Dual-stack live hook + rollback | Both hooks activated with empty sets; emergency rollback removed hooks |
| Systemd bouncer dependency | Required enforcement unit loaded when both temporary test masks were removed |
| Automatic synchronization | Both blacklist families populated during a timed live test |
| Rollback while both services enabled | Both startup registrations removed; bouncer masked; hooks removed; sets emptied |
| Fresh WireGuard SSH with live protection | Successful |
| Production reboot | All nine relevant services active/enabled, both CrowdSec families restored, fresh management access succeeded |

The final production reboot occurred on 2026-09-27 UTC. The reported acceptance-time blacklist totals were 23,006 IPv4 entries and 364 IPv6 entries; these are time-dependent observations, **not invariant acceptance thresholds**. The three CrowdSec bootstrap/enforcement/bouncer units reported successful execution.

## Operations and recovery boundary

A root-owned emergency rollback executable is installed and was tested in disabled and enabled states. It disables persistent enforcement and bouncer startup, reinstates both bouncer masks, removes only the Edge1-owned input hooks, clears the bouncer-managed sets and preserves the non-enforcing bootstrap. Independent systemd rollback timers were used during activation tests and disarmed only after confirmation.

**Follow-up gates:** verify a production UFW reload while live hooks are attached under timed recovery; establish routine feed false-positive review and an exception process; test long-running health and recovery telemetry. Separate approval and acceptance are required before any forwarded-traffic enforcement.

**Source and trust:** this file summarizes the operator's deployment-console reports; it is not an independent contemporaneous API poll. The private Edge1 MCP status endpoint was unavailable during the documentation session. Do not commit production secrets, raw threat-feed IP lists, internal-only diagnostics or complete runtime configuration here.
