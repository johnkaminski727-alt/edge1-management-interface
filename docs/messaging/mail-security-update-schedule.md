# Private mail security update schedule

All jobs are on Edge1 and do not read customer mail or call AVA.

| Component | Schedule | Success requirement |
| --- | --- | --- |
| Official ClamAV definitions | Hourly at minute 10 UTC | FreshClam succeeds, running daemon has the daily database version, clean and EICAR probes pass |
| Packaged Rspamd rules and ClamAV engines | Daily 03:15 America/Regina (09:15 UTC) | Existing signed APT sources refresh, only installed named mail packages upgrade, configuration validates, services and clean/EICAR/GTUBE probes pass |
| Local Bayesian corrections | Existing security scan every minute | Operator Spam/Not spam queue trains local Rspamd; automatic learning is disabled |
| Custom domain thresholds and phishing policy | Versioned deployment or explicit operator change | Upstream package updates preserve local configuration; no automatic policy rewriting |

`wwcx-mail-update-definitions.timer` and `wwcx-mail-update-packages.timer` are persistent: a missed scheduled run executes after recovery. No reboot or repository addition is permitted by these jobs. APT dependencies may also upgrade as required by the named mail packages. No package removal is allowed. Mail package config backups are root-only and bounded to seven maintenance runs.

Root writes aggregate job state in `/var/lib/wwcx-mail-updates/{definitions,packages}.json`, readable by the private Mail Room. Failed attempts never advance last success. Last results, success times and schedules appear in Daily Summary, and the connection banner warns on failure or staleness. Reports show update health at report-generation time, not a historical reconstruction of that day.

Definitions warn after three hours without verification; package maintenance warns after 36 hours. After 24 hours without a verified definition check, scanning blocks new mail. A failed scan stays pending. Unchanged signature files remain fresh when the updater successfully verifies them; file modification time alone is not an update-success measure.

The distro FreshClam daemon is masked to avoid two updaters. FreshClam notifies the custom private scanner. Concurrent database reload is disabled to fit the scanner's memory limit. The stock ClamAV daemon remains masked. An invalid Rspamd config stops Rspamd and therefore holds pending mail. Maintenance records failure and retains the prior successful timestamp; it does not pretend to roll back an installed package.

Deploy from an immutable root-owned release with `deploy/messaging/install-mail-security-updates.py --release PATH`. Initial definition job starts asynchronously. Run the package service once for acceptance, then inspect job records and timer next-run times. Confirm stock daemons stay masked and private scanners remain loopback/UNIX only. Provider commissioning and outbound sending are unchanged.
