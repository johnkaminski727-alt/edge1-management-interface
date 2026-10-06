# Edge1 Suricata tuning — 2026-10-05
Target: edge1. Passive IDS; wg0 pcap capture.

Baseline review:
- 2,202 alerts in the current EVE file; 2,179 (98.96%) SID 2200036 TCP option invalid length.
- Other signatures: OpenAI API DNS info (16), ipify DNS info (4), ipify TLS info (2), QUIC error (1).
- These labels do not prove compromise. No assertion that TCP warnings are benign.
- About 2.45 million packets; capture kernel_drops=0 and kernel_ifdrops=0.
- CPU lifetime average 0.7%, RSS approximately 1.33 GiB; existing low detection profile.
- Private addresses observed: 10.77.0.1, 10.77.0.3, 10.77.0.5.
- Kernel route table confirms 10.77.0.0/24 on wg0; Edge1 public IP 89.126.248.191.

Applied:
- HOME_NET=[10.77.0.0/24,89.126.248.191/32], replacing all RFC1918 networks.
  Revisit this if new LAN routes, IPv6 or additional protected networks are introduced.
- /etc/wwcx-suricata/threshold.config: SID 2200036, limit 1 alert per source per 60 seconds.
  Signatures stay enabled; repeated alerts are aggregated by threshold suppression.
- No changes to inspection depths, capture buffers, CPU threads, rule sources, firewall or IPS.
- Corrected diagnostic suricata.log group to root with mode 0660; owner remains suricata.
  A startup drop-in restores this group before each launch (Suricata resets its log group).
  This lets the constrained root startup process open it before dropping to suricata.
- Existing seven-rotation daily compressed logrotate policy validated in debug mode.
- Daily guarded rule-update timer remains configured; no extra timer introduced.

Validation:
- Full 53,098-rule configuration test as unprivileged suricata passed; 0 failed rules.
- Synthetic offline PCAP verified 5 malformed TCP packets produce 2 warning alerts
  across a 60-second boundary; harmless UDP HOME_NET canary produces 1 alert.
- Offline probe isolated; test SID 9900001 was NOT added to production rules.
- Passive sensor restarted to apply configuration without simultaneous rule-engine memory.
- Production HTTPS health remains 200.

Backup: /var/backups/edge1-suricata-tuning/20261005T032905Z
Contains original suricata.yaml, sensor environment, logrotate and baseline JSON.
Rollback: restore original suricata.yaml, then validate with suricata -T and restart the sensor.
Remove the new threshold file only after reverting its config reference.
The independent 30-log-startup-permissions.conf drop-in may be retained as a permission fix.

Coverage:
wg0 observes decrypted WireGuard traffic, not every ens3/public-interface attempt.
TLS payload remains encrypted; network TLS metadata is not decrypted application data.
No broad suppression of informational OpenAI/ipify signatures was applied.
