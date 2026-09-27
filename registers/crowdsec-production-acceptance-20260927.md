# CrowdSec production acceptance register — 2026-09-27

**Reference:** [Sanitized engineering acceptance](../docs/security/crowdsec-dual-stack-production-acceptance-20260927.md). **Evidence basis:** operator-supplied Edge1 shell and Windows SSH output during Assignments 112–133. Private detailed acceptance bundle is intended for Project Big Bird / Edge1 Operations Center / Implementation.

| ID | Control or deliverable | Observed status | Evidence |
|---|---|---|---|
| CS-01 | Non-enforcing, idempotent dual-stack bootstrap | Passed | 112–113 |
| CS-02 | Staged CrowdSec table survival on ordinary UFW reload | Passed | 115 |
| CS-03 | Bootstrap persistence after controlled reboot | Passed | 119 |
| CS-04 | IPv4 and IPv6 input hooks + tested rollback | Passed | 123B |
| CS-05 | Effective bouncer startup dependency with dual masks temporarily removed | Passed | 125B |
| CS-06 | Automatic bouncer set synchronization under live hooks | Passed | 126 |
| CS-07 | Hardened rollback when both services enabled | Passed | 129 |
| CS-08 | Permanent service activation and fresh WireGuard SSH | Passed | 130–131 |
| CS-09 | Production reboot and automatic dual-stack restoration | Passed | 132–133 |
| CS-10 | Active-hook UFW reload rehearsal | Open | Separate controlled test with timed independent rollback |
| CS-11 | Feed false-positive monitoring and exception governance | Open | Define review cadence, operator response and expiry |
| CS-12 | Routed VPN forwarding protection | Accepted separately | Assignments 134–146; [forwarding acceptance](crowdsec-vpn-forward-acceptance-20260927.md) |

**Update:** The nine-service summary below refers to the earlier INPUT-only checkpoint. The subsequently completed VPN FORWARD milestone passed a ten-service post-reboot check at 04:03 UTC; refer to the separate register.

**Last observed acceptance:** all nine relevant units active/enabled after production reboot; two independent hooked input chains; both blacklists populated. Counts are time-dependent and must not be used as fixed pass thresholds. Operator's direct and WireGuard SSH management connections succeeded.

**Security boundary:** no private IPs, secret key values, detailed access topology, full threat-feed lists or production configuration dumps in this public register. The full runbook, evidence ledger and decision/risk registers must remain in the private operational workspace. Live Edge1 private-library ingestion is a separate action and was not confirmed by the read-only MCP connector during this documentation session.
