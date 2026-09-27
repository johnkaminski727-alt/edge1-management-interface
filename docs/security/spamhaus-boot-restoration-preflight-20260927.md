# Spamhaus reboot restoration: pinned-candidate preflight (2026-09-27)

**Status:** Draft validation only, no startup unit installed, no reboot, no firewall modifications.

Assignment 229 observed the live table with 1,610 IPv4 and 85 IPv6 aggregated set elements, input and forward hooks, and existing enabled UFW, CrowdSec, CrowdSec firewall bouncer and SSH services. The saved IPv4 feed was 2.9 hours old and IPv6 feed 54.9 hours old at inspection. The current parser rejects source timestamps older than 72 hours or more than 15 minutes in the future. Consequently the old pinned IPv6 candidate can become ineligible for reboot restoration after roughly 17 hours; it MUST NOT be restored automatically when stale.

The new `tools/networking/spamhaus_boot_preflight.py` is a check-only integrity and age gate:
- Validate every SHA-256 entry from the protected candidate manifest, reject missing/symlinked files, verify the candidate against the official JSON parser's freshly rendered representation.
- Confirm the independent root-owned rollback program matches the staged copy.
- Validate IPv4 and IPv6 feed timestamps and network contents using existing parser rules.
- Inspect no live nftables state, run no nft command, do not install systemd services and never restore a firewall table. It accepts explicit stage/parser/recovery paths and prints counts only.

## Future boot-time restoration design (NOT implemented or approved by this draft PR)

- Use a separate dedicated `edge1-spamhaus-restore.service` with ordering after local filesystems and prerequisite firewall orchestration; audit ordering with UFW and CrowdSec first. Do not enable `nftables.service` or reload a saved complete ruleset.
- Use a root-owned production candidate store separate from archival backups. Boot restore must refuse a stale or tampered candidate, a missing rescue program, uncertain clock validity, unexpected existing table or unclear dependency state. Log why filtering stays absent instead of applying obsolete policy.
- Before any *future* restart test that would apply rules, arrange independent console/rescue and a scoped systemd rollback timer. Verify new SSH and expected forwarded paths, then disarm only after acceptance. Boot-time unattended restoration needs its own safe unattended success criteria and failure policy, not reliance on interactive SSH.
- Refreshed feeds and periodic updates are a separate guarded policy; the existing `bigbird-spamhaus-filter.timer` must remain absent/disabled. If feeds are stale at boot and retrieval cannot be trusted, fail closed on the restoration operation without changing UFW, CrowdSec or SSH (the Spamhaus layer may temporarily be absent).
- Validate reboot persistence only during a separately approved change window. Never imply this preflight establishes persistence.

The protected checkpoint `/var/backups/edge1-spamhaus-preflight-a4hFSx61` and candidate `/var/backups/edge1-spamhaus-candidate-5Y7w3VKA` are existing Edge1-local paths; their contents must remain private and must not be committed to the repository.
