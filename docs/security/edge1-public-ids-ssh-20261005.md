# Edge1 public IDS and SSH repeat-offender escalation

Activated 2026-10-05 UTC; TARGET: edge1.

Suricata's existing passive pcap sensor now captures wg0 and ens3, using one rule
engine. /etc/wwcx-suricata/suricata.yaml explicitly lists both devices;
/etc/default/wwcx-network-sensor selects --pcap with no device override.
No new listeners, inline IPS, decoy login or firewall feed was added.
The existing 53,098 rules and SID 2200036 source-per-minute threshold remain.
The managed daily updater reads this same configuration. The consolidation
command check accepts both --pcap and --pcap=DEVICE forms.

Native Fail2Ban sshd history now selects 172800, 604800, 2592000, 63115200 seconds
(48 hours, 7 days, 30 days, 730.5 days); final tier repeats. Existing five-failure,
ten-minute filter, systemd journal, UFW action and loopback/WireGuard exemptions
remain. Fail2Ban's native observer can accelerate detection for known offenders.
Retained prior bans count; this change does not erase history or retroactively
change old expired bans. Repeat history is retained for three years, rather than
indefinitely. CrowdSec remains independent with its existing policy.

Configuration sources are deploy/security/edge1-ssh-escalation/*.local. Install
zz-edge1-ssh-escalation.local in /etc/fail2ban/jail.d/ and zz-edge1-history.local
in /etc/fail2ban/fail2ban.d/. Run fail2ban-client -t before fail2ban-client reload.

Validation: native Fail2Ban formula yielded all four exact tiers plus repeated
final tiers; configuration test and live reload passed. Live settings confirm
increment enabled, 172800 initial, 63115200 maximum, 94672800 history retention.
Full Suricata configuration validation passed as user suricata; startup loaded
53,098 rules with zero failures and confirmed two capture devices. Live ens3
EVE records were observed. Service health, capture drops, both-interface events
and memory are recorded in the backup's acceptance.json.

The ens3 virtual NIC reports an unsupported offload-setting ioctl; capture runs
with automatic checksum handling. TLS and WireGuard outer payloads remain
encrypted on ens3; decrypted WireGuard traffic is inspected on wg0. Packet
visibility is not a guarantee of detecting every attack. No production ban was
injected for testing.

Backup: /var/backups/edge1-public-ids-ssh/20261005T034234Z. manifest.json identifies
original files and newly created overrides; fail2ban.sqlite3 is a consistent
pre-change backup. Rollback restores original YAML/environment, removes only
the two new Fail2Ban overrides, validates configurations, restarts the sensor
and reloads Fail2Ban. Do not restore the old database as routine rollback: retain
new history. SSH service need not be restarted.
