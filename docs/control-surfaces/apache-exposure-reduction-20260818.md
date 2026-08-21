# Edge1 Apache Control Surfaces exposure reduction

Date: 2026-08-18
Status: live change accepted locally; repository-managed policy added for reproducibility

**Superseded redirect target:** the root/`/index.html` redirect target below (`https://creekco.ca/time/`) was changed the next day to `https://ww.cx/time/`. See `docs/control-surfaces/edge1-front-door-20260819.md` for the change decision and `docs/control-surfaces/edge1-front-door-live-acceptance-20260819.md` for its live acceptance. The FreePBX/UCP restriction described below remains current and is not affected by that change.

## Live result

The Edge1 Apache HTTPS vhost now includes `/etc/apache2/wwcx-edge1-control-surfaces.conf`.

The managed policy:

- redirects ordinary `https://edge1.ww.cx/` and `/index.html` requests to `https://creekco.ca/time/`;
- preserves the existing certificate and explicit Operations API, timekeeping MCP, Electrum Watch and other parent-vhost routes;
- restricts native FreePBX `/admin` and `/ucp` to loopback, WireGuard `10.77.0.0/24`, Tailscale IPv4 `100.64.0.0/10`, and Tailscale IPv6 `fd7a:115c:a1e0::/48`;
- performs no firewall, DNS, SIP, Asterisk, Kamailio, certificate, carrier, call, or message change.

## Accepted live checks

The live 2026-08-18 change passed `apache2ctl configtest` before and after reload. Apache remained active.

Observed post-change behavior from the Edge1 host using its public source address:

- root: HTTP 302 to `https://creekco.ca/time/`;
- `/index.html`: HTTP 302 to `https://creekco.ca/time/`;
- `/admin/`: HTTP 403;
- `/ucp/`: HTTP 403.

Using the WireGuard source address `10.77.0.1`:

- `/admin/`: HTTP 302 to FreePBX `config.php`;
- `/ucp/`: HTTP 200.

The existing `/api/operations/` proxy continued to reach the loopback Operations API, and the accepted Kamailio/Asterisk/Operations API/Edge1 Operator/BigBird listener ownership remained unchanged.

The browser session used during follow-up was itself on the private management path, so its continued FreePBX access is not WAN evidence. Treat the server-side public-source 403 checks plus future independent off-private-network checks as the public exposure acceptance evidence.

## Managed source

Repository assets:

- `deploy/control-surfaces/wwcx-edge1-control-surfaces.conf`
- `deploy/control-surfaces/install-edge1-control-surfaces-apache.sh`

The installer defaults to `--check`. `--apply` creates a root-only timestamped backup and rollback script, installs the policy, attaches the include idempotently, requires a successful Apache config test before reload, reloads Apache only, and records SHA-256 evidence.

## Live evidence

Initial live evidence directory:

`/var/lib/wwcx-deployment-evidence/control-surfaces-apache/20260818T181554Z`

The functional change completed successfully. The first interactive command attempted to write `SHA256SUMS` as the unprivileged shell user into the root-only evidence directory and received `Permission denied`; this did not undo the applied Apache configuration. Complete the evidence hash as root before final workstream closeout.

## Rollback

The live evidence directory contains `rollback.sh`, created before Apache reload. The repository installer also creates a timestamped rollback under `/var/backups/wwcx-edge1-control-surfaces-<UTC timestamp>/rollback.sh` for future managed applications.
