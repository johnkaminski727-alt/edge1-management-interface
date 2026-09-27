# Edge1 Spamhaus production recovery design — 2026-09-27

**State:** proposal and isolated fixture tests only. Does not install, arm or execute production firewall changes. No authorization to activate the Spamhaus filter.

## Verified operator evidence

- Assignment 211: Edge1 has live UFW, CrowdSec, CrowdSec firewall bouncer and SSH; `nftables.service` disabled/inactive; Tailscale absent. `systemd-run` available. Operator confirms independent hosting console and rescue-mode access.
- Assignment 212: an independent transient systemd timer removed a simulated firewall marker and reported successful completion after SSH-driven scheduling. No nftables operations were executed by the drill.
- Assignment 213: an isolated mock-nft rollback removed only the simulated `inet bigbird_spamhaus` table, succeeded on repeat and correctly failed on simulated deletion error. Live Spamhaus production table remained absent. These results **do not demonstrate live rollback of a deployed filter**.
- Existing proposed filter uses dedicated `inet bigbird_spamhaus` input/forward base chains at priority `-110`; observed UFW/CrowdSec chains have distinct priorities. IPv4 forwarding enabled; IPv6 forwarding disabled at assessment. Priority noncollision alone does not establish traffic safety.

## Scoped recovery primitive

`tools/networking/spamhaus_scoped_recovery.py` is check-only by default. It queries `nft -j list tables`, and rejects query/JSON errors rather than treating them as absence. Only explicit `--execute` can delete exactly `inet bigbird_spamhaus`; it verifies table absence afterward. It does not flush the ruleset, restart nftables, stop UFW or CrowdSec, enable filtering, edit DNS, or modify connection policy. Tests in `tests/validate_spamhaus_scoped_recovery.py` mock nft and cover exact table removal, idempotency, check-only, failed query, malformed response and deletion failure.

## Requirements before any live activation

1. Review and merge the isolated rollback primitive after CI and Edge1 fixture testing. Independently install the reviewed root-owned recovery script outside any mutable Git checkout **only in a separately approved deployment**.
2. Capture a backup of current ruleset and relevant UFW/CrowdSec service states in a root-only directory. A ruleset backup containing addresses must not enter GitHub or public logs. Record a hash for the candidate and expected dedicated table identity.
3. Pre-arm a verified transient systemd rollback timer that invokes the independent, root-owned scoped recovery script, with a suitable timeout and journal inspection. The timer must not rely on an ongoing SSH session.
4. With console/rescue credentials independently tested, coordinate the change window and external probe. Before any candidate application, verify the rollback timer is active and its command is exactly scoped.
5. Only after a separate explicit approval, apply reviewed current-feed policy and check an **independent new SSH session** plus expected forwarding paths. If any test fails, leave the rollback armed. Do not cancel the rollback based on survival of an existing SSH session.
6. If all checks succeed, explicitly disarm the rollback after approval and document the observed live ruleset, independent connectivity verification, service/timer state and recovery path. Any subsequent schedule-based feed application requires distinct approval, limits and fail-safe policy.
7. Verify failure cases including host reboot, runner errors and out-of-band rescue instructions separately. Neither a one-time simulated timer drill nor mocked deletion is evidence of full automatic recovery under real packet filtering.

**Current production boundary:** Spamhaus filtering disabled. Existing check-only feed updater `tools/networking/spamhaus-nft-update.sh` and deliberately blocked `tools/networking/install-spamhaus-filter.sh` remain unchanged.
