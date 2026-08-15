# WW.CX Public NTP Firewall Live Acceptance — 2026-08-15

## Scope

This record captures the successful attended publication of the approved IPv4 NTP firewall rule for the WW.CX Time Authority public NTP service on Edge1.

This is a firewall/publication acceptance record, not yet the final outside-in Internet reachability acceptance. A successful NTP query from a host outside Edge1 remains the final service-acceptance step.

## Accepted live state

Observed on `edge1.ww.cx` after the corrected firewall helper was merged and deployed:

- repository revision included merge commit `347f350f18372dfddef40107bd7dbb241dda7247` from PR #324;
- guarded helper `deploy/publish-time-authority-ntp-firewall-edge1.sh` completed successfully;
- local packet-level WW.CX NTP smoke test passed after firewall publication;
- `chronyd` remained synchronized at stratum 4 with leap status `Normal`;
- current selected upstream was `time.cloudflare.com`;
- the live `inet wwcxfw input` chain contains:
  - `ip daddr 89.147.109.253 udp dport 123 accept comment "wwcx:public-ntp-v4"`;
- `/etc/nftables.conf` contains the same persistent boot-time IPv4 UDP/123 rule;
- `chronyd` is listening on `0.0.0.0:123` and `[::]:123`;
- public IPv6 firewall publication remains intentionally unchanged;
- `nftables.service` was intentionally not reloaded, preserving runtime Big Bird blocklist/logging controls not represented in the base persistence file;
- rollback evidence was written to `/var/lib/wwcx-deployment-evidence/public-ntp-server/firewall-20260815T211902Z`.

## DNS state

During the immediately preceding preflight, the following names resolved on Edge1 to `89.147.109.253`:

- `ntp.ww.cx` — canonical NTP service name;
- `time.ww.cx` — alternate service name;
- `edge1.ww.cx` — Edge1 host name.

## Incident and recovery

The first attended firewall publication attempt failed safely because nft received the comment token without literal quotes and parsed the colon in `wwcx:public-ntp-v4` as syntax. The helper rolled back the current-run persistent edit and did not publish a live rule.

PR #324 corrected this by rendering the targeted live insert as an nft batch containing a literal quoted comment, syntax-checking that exact batch with `nft -c -f`, and only then applying it with `nft -f`. Repository validation and Edge1 Operator Validation both passed before merge.

The corrected attended retry then completed successfully.

## Acceptance boundary

Accepted as of this record:

- chronyd host clock discipline and NTP service are healthy;
- local NTP packet exchange is healthy;
- DNS is published for the reviewed IPv4 address;
- IPv4 UDP/123 is allowed in both the live and persistent Edge1 firewall configuration;
- current runtime Big Bird firewall protections were preserved;
- rollback evidence exists.

Still required before declaring the public endpoint fully accepted:

1. send an NTP request to `ntp.ww.cx` from a host/network outside Edge1;
2. verify a valid server-mode NTP response with synchronized leap status and sensible stratum;
3. optionally repeat against `time.ww.cx` and from a second independent network;
4. record the outside-in result as the final public NTP service acceptance.

## Deferred

Not changed or accepted in this phase:

- public IPv6 NTP/AAAA publication;
- NTS / TCP 4460;
- certificates;
- unrelated firewall, DNS, routing, authentication, or service policy.
