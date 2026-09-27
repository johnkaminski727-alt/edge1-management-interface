# Edge1 CrowdSec IPv4 VPN FORWARD production acceptance — 2026-09-27

**Scope:** Separate, later milestone following the dual-stack INPUT acceptance. **Evidence basis:** operator-supplied Edge1 and Windows console outputs from Assignments 134–146; not an independent new server API poll. Public documentation is sanitized; private runbook and detailed register are archived in the Edge1 Operations Center project library.

## Accepted runtime boundary

UFW remains the baseline INPUT and routed firewall. CrowdSec's bouncer owns the IPv4/IPv6 blacklist membership in set-only mode. The additional `edge1-crowdsec-forward.service` applies an IPv4 nftables FORWARD hook at priority -10; two drop/counter rules check blacklist destinations for outbound WireGuard→internet packets and blacklist sources for internet→WireGuard forwarded packets. Existing dual-stack INPUT hooks and WireGuard management exemptions remain separate. IPv4 NAT and routing were preserved. IPv6 forwarding is disabled; IPv6 VPN transit protection was **not** deployed.

## Acceptance checkpoints

| Checkpoint | Operator-observed result |
|---|---|
| 134–136 | UFW/WG/NAT/bouncer healthy; two forwarding rules staged, activated under an independent rollback timer and removed safely. |
| 137–140 | Windows used WireGuard for public destinations. Four test packets to a reserved address were recorded at the outbound forwarding drop counter: **4 packets, 240 bytes**; inbound drop count was 0. Emergency cleanup removed the test IP and temporary forward hook without affecting INPUT protection. |
| 141–142 | Dependency-ordered systemd launcher and forwarding-only emergency recovery validated; recovery disabled the service and startup and removed the hook when enabled. |
| 143–144 | Permanent activation passed with 23,006 IPv4 blacklist entries at acceptance; Windows WireGuard route, TCP/443, HTTP 200 and fresh VPN SSH succeeded. |
| 145–146 | Reboot initiated after ten services, three hooked chains and both recovery scripts passed preflight. Reconnected over WireGuard after **04:03 UTC** reboot; all ten services active/enabled and four CrowdSec units returned success/exit 0. Both INPUT hooks and IPv4 FORWARD hook restored; observed blacklist counts 23,006 IPv4 / 364 IPv6. |

**Limits:** The inbound FORWARD rule was structurally validated but not exercised by incoming malicious-source test traffic. Counts are time-dependent observations, not exact future acceptance thresholds. This is blacklist IP enforcement, not complete inspection or malware detection. A live-hook UFW reload test, false-positive governance and freshness telemetry remain open.

## Recovery split

The **forwarding-only** emergency command on Edge1 is `sudo /root/edge1-crowdsec-forward-emergency.sh`; its enabled-state behavior was tested. It disables forwarding startup and removes only the forward hook, retaining the original INPUT protections and bouncer. The broader `/root/edge1-crowdsec-sync-rollback.sh` disables the INPUT/bouncer deployment and clears both sets; do not use it as a substitute for the forwarding-only recovery. Both scripts require authorized Edge1 administrator access. Preserve the independently accessible hosting console during high-risk network changes.

## Next integration work

The original nine-phase Network Operations Center proposal is **not** completed by this workstream. Integrate sanitized hook presence, feed freshness, packet counters, service and recovery state into the accepted read-only Operations Center; verify source/observed-state authority before building the candidate/review/apply workflow. See [original input milestone](crowdsec-dual-stack-production-acceptance-20260927.md).
