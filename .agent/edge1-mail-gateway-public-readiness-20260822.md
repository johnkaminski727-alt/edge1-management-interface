# Edge1 Mail Gateway — Public Readiness State

Date: 2026-08-22
Status: implementation branch; read-only readiness phase

## Accepted live basis

Authenticated Edge1 raw-archive migration succeeded after the live clean `main` checkout was fast-forwarded through `20b3f6c2a5a3da6484b433f6f171c3c713ef920e`.

Verified operator evidence:

- raw archive contract `wwcx.edge1-mail-gateway-raw-archive.v1`;
- `raw_archive_verified=true`;
- Creekco synthetic acceptance produced one authoritative `production_native` Mail Room record;
- Mail Room record count `4 -> 5`;
- Postfix remained active;
- TCP/25 remained loopback-only;
- rollback was not performed;
- backup/evidence path `/var/backups/wwcx-mail-gateway/raw-archive-migration-20260822T082911Z`.

## This phase

Adds a read-only public-ingress readiness preflight for `mail.ww.cx`.

It verifies the accepted archive-first Postfix state and collects evidence for:

- public IPv4 derived from the default-route interface;
- `mail.ww.cx` IPv4 resolution;
- PTR existence and forward-confirmation;
- TLS certificate readiness without reading private-key contents;
- relay denial;
- raw archive ownership/mode;
- filesystem free space;
- Postfix queue state;
- listener state;
- read-only nftables evidence when available.

## Safety boundary

This phase does not:

- expose TCP/25 publicly;
- edit Postfix;
- reload/restart Postfix;
- change firewall rules;
- request/install TLS certificates;
- change DNS or MX;
- change provider mailboxes;
- enable outbound delivery;
- migrate `ww.cx`.

## Remaining production gates

Public listener activation, firewall changes, certificate changes, DNS/PTR changes, an external TCP/25/relay probe, and the first `creekco.ca` MX cutover remain separate explicitly authorized operations.
