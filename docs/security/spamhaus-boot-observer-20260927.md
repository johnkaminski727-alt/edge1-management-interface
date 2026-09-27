# Spamhaus boot observer — staging only (2026-09-27)

**This release is NOT reboot persistence.** It adds an inert check-only systemd unit and a static test. The unit is not installed or enabled. Do not deploy its files merely to obtain automatic firewall restoration.

The unit depends on a future *separately approved* root-owned candidate directory under `/var/lib/edge1-spamhaus/boot-candidate` and independently installed copies of the parser and boot preflight under `/usr/local/libexec/edge1-spamhaus`. Neither these copies nor the candidate directory are created by this PR. The existing protected backup and staging directory under `/var/backups` are archival records, not an immutable indefinitely valid boot policy.

Its only operation is to validate SHA-256 manifest integrity, recovery identity, IPv4/IPv6 source freshness (at most 72 hours) and exact candidate rendering. It does not list, create or replace live nftables tables. It contains no `[Install]` section, no shell installer and no means to enable automatic updates.

Before approving any true persistence service, independently review UFW/CrowdSec boot ordering, time synchronization (timestamps must be trustworthy), state at boot if a live table already exists, policy if offline or feeds are stale, and how to arm and independently verify a rollback when nobody is logged in via SSH. Do not restore an expired pinned candidate and do not flush or reload UFW/CrowdSec tables.

Operator Assignment 231: live Spamhaus present; independent root-owned rollback available; pinned candidate still passed freshness and integrity checks during assessment. Saved IPv6 feed age at earlier inspection was 54.9 hours, so this candidate will eventually fail preflight without refresh.
