# Spamhaus boot readiness gate — staging only

Assignment 235: Edge1 is synchronized to ISNIC Chrony (tracking showed Normal leap status). `chrony.service` is enabled and active; `chrony-wait.service` is disabled and inactive; `time-sync.target` is inactive. Thus merely ordering a unit `After=time-sync.target` does **not** prove synchronization at boot.

This new read-only `tools/networking/spamhaus_boot_readiness.py` explicitly inspects `timedatectl NTPSynchronized=yes`, Chrony tracking `Leap status : Normal`, and active SSH, UFW, CrowdSec and firewall-bouncer services. It distinguishes an existing Spamhaus table from an absent table using a full JSON nft table inventory and fails closed on inventory errors. It never applies or deletes nft rules, schedules units, or refreshes DNS/feeds.

This is only the **dependency gate**. It does not itself establish timeouts or boot execution ordering, validate feed age or hashes, install or activate a filter. Pair it with the existing `spamhaus_boot_preflight.py` candidate validation only in a separately reviewed restoration design. Prefer a bounded wait/retry with an explicit maximum duration; avoid an indefinite boot wait if Chrony cannot synchronize. No automatic restoration should run if either gate fails.

Existing live Spamhaus filter and protected backups remain unchanged by this PR. No boot service or timer is installed or enabled.
