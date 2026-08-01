# Asterisk Transport and Exposure Audit Acceptance — 2026-08-01

## Live execution

Authenticated read-only execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

Authoritative evidence:

```text
/var/lib/wwcx-deployment-evidence/asterisk-transport-exposure-audit/20260801T012059Z/audit.txt
SHA-256: f509e00194bc93e04ef9647c35e09f3adb39d6a01fdf2d2af8e65648684229ff
```

An earlier equivalent run is retained at `20260801T011930Z`; the `20260801T012059Z` run is the accepted complete capture.

## Accepted healthy state

- Asterisk `22.10.1` remained active for more than one hour and forty minutes after update.
- Boot persistence remained enabled.
- Zero active channels, zero active calls, and zero processed calls were observed.
- `chan_pjsip` and the `res_pjsip` module family were running.
- Kamailio retained UDP and TCP `5060` ownership on public, WireGuard, and loopback addresses.
- Asterisk retained loopback UDP `127.0.0.1:5061` ownership.
- Asterisk HTTP remained loopback-only on `127.0.0.1:8088`.
- Asterisk HTTPS completed a local TLS 1.3 handshake on `8089`.
- The certificate file is mode `0600`, owned by `asterisk:asterisk`, and expires on `2028-07-10`.
- No service, package, listener, route, certificate, firewall, call, CAP feed, or alert-delivery change was performed by the audit.

## Unresolved PJSIP discrepancy

The PJSIP channel driver is loaded and Asterisk owns `127.0.0.1:5061`, but `pjsip show transports` and `pjsip show endpoints` return no objects.

Two configuration fragments contain the same transport section name:

```text
/etc/asterisk/pjsip.transports.conf:[0.0.0.0-udp] bind=0.0.0.0:5060
/etc/asterisk/pjsip.transports_custom.conf:[0.0.0.0-udp] bind=127.0.0.1:5061
```

The generated transport file must not be edited directly. Runtime transport ownership remains unresolved until the actual include order and any Sorcery/realtime mappings are measured.

## Audit parser correction

The first audit's include-order helper checked generic comment lines before checking Asterisk `#include` and `#tryinclude` directives. It therefore could incorrectly report that no include directives existed. This affects only that one observation; it does not invalidate listener, module, certificate, boot, or firewall observations.

A corrected focused follow-up audit now checks include directives before treating `#` lines as comments.

## HTTPS and firewall classification

Asterisk HTTPS is configured on `[::]:8089`. Because `net.ipv6.bindv6only=0`, that wildcard socket may accept both IPv6 and IPv4 connections subject to firewall policy.

The host has:

- public IPv4 `89.147.109.253`;
- WireGuard IPv4 `10.77.0.1`;
- an `inet wwcxfw` input base chain with policy `drop`;
- a legacy `ip filter` INPUT base chain with policy `accept`;
- no rule that explicitly names ports `5060`, `5061`, `8088`, or `8089` in the summarized ruleset.

The default-drop chain is encouraging, but the summary does not prove that `8089` is unreachable. Generic interface, source-address, established-flow, jump, or accept rules may still permit it. Full input-chain rule paths must be reviewed before deciding whether to rebind, firewall, reverse-proxy, or retain the listener.

## Consumer-reference limitation

The first reference search produced substantial false-positive noise from Git metadata and Python virtual environments. No actual reverse-proxy or application consumer was established by that output. The focused follow-up excludes `.git`, virtual environments, and cache trees.

## Decision boundary

Accepted:

- the health and ownership observations above;
- boot enablement;
- local TLS functionality;
- protected evidence and hash;
- continued offline-only alerting laboratory state.

Not accepted or authorized:

- editing generated FreePBX PJSIP files;
- reloading or restarting Asterisk;
- changing the `8089` bind address;
- changing nftables or Fail2ban policy;
- replacing the certificate;
- enabling endpoints, CAP feeds, Actual alerts, calls/pages, or attention-tone transmission.
