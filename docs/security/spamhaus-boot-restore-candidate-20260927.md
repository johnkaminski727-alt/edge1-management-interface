# Spamhaus boot restore candidate — staging only

Assignment 235 confirmed Chrony is active and synchronized, network-online is active, UFW/CrowdSec/bouncer are active, and no Spamhaus persistence service exists.

This PR stages a conservative boot restore helper and a non-enableable systemd unit. Nothing is installed by the PR itself.

Runtime gates:
- wait for Chrony synchronization;
- run the existing pinned-candidate integrity/freshness preflight;
- refuse replacement when the dedicated Spamhaus table already exists;
- run nftables --check before any apply;
- apply only the single pinned candidate file;
- verify the dedicated table exists after application;
- never flush the global ruleset, enable nftables.service, refresh feeds, or alter UFW/CrowdSec.

The service deliberately has no [Install] section. Actual installation, copying of root-owned executables/candidate into /usr/local/libexec and /var/lib, enablement, rollback arming, and reboot testing require a separate approved deployment.

The pinned candidate remains time-limited by the parser's 72-hour feed-age ceiling. If the feed is stale, boot preflight fails and this service does not apply it.
