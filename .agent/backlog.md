# Backlog

## Completed live phases

- [x] Security Correlation and Network Defense deployed and accepted.
- [x] Suricata drill-down, caching, normalization, and enrichment deployed.
- [x] Spamhaus, Fail2ban, and nftables truthful live states accepted.
- [x] DNS remains `not_staged`; DNS enforcement remains false.
- [x] Network Defense freshness threshold activated and accepted at `600` seconds.
- [x] Verified enforcement count remained `1` before and after activation.
- [x] Timer state and traffic controls remained unchanged.

## Completed repository phases

- [x] Network Defense freshness implementation and closeout through PR #127.
- [x] Protected Suricata retention design and closeout through PR #129.
- [x] Public access-boundary design and closeout through PR #131.
- [x] Minimized public summary implementation and closeout through PR #133.
- [x] Edge1 project completion operator bundle merged through PR #134 as `00904a2d26b4b3b14e18144c9bccd29b3a9f10b1`.
- [x] Runtime-wiring validation corrected through PR #136.
- [x] Pass PR #136 `Validate repository` run 636.
- [x] Pass PR #136 `Edge1 Operator Validation` run 468.
- [x] Merge PR #136 as `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`.

## Completed authenticated host sequence

- [x] Establish authenticated SSH access to `edge1.ww.cx` as `wwadmin` without sharing credentials.
- [x] Fast-forward clean `/opt/edge1-management-interface` checkout to authoritative `main`.
- [x] Run `sudo bash tools/security/edge1-project-completion-preflight.sh`.
- [x] Capture protected preflight evidence at `/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z`.
- [x] Safely stop the first activation during pre-mutation validation when the stale test failed.
- [x] Pull the PR #136 correction.
- [x] Run `sudo bash deploy/activate-network-defense-freshness.sh` successfully.
- [x] Confirm threshold `600`, local/public acceptance, unchanged timer/enforcement/DNS/traffic-control state, and successful completion.
- [x] Capture protected activation evidence at `/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z`.
- [x] Update authoritative records with exact host evidence paths and live acceptance results.

## Separate future programs

Require new branches, measured host evidence, exact-head CI, and separate deployment acceptance:

- [ ] protected Suricata-retention runtime implementation;
- [ ] minimized public-summary server-side publication design;
- [ ] authenticated detailed-operations browser/session design;
- [ ] staged public-boundary cutover and detailed-artifact removal.

These items are not blockers to the completed Network Defense freshness project.

## Exact authorization still required

- `/var/www` publication or removal;
- Apache/proxy/auth/header reload or route changes;
- authentication, certificate, listener, DNS, firewall, or traffic changes;
- public or production cutover;
- deletion of retained status, report, incident, or evidence data.
