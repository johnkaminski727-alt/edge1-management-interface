# Asterisk Transport Policy Follow-up Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/asterisk-transport-policy-followup/20260801T012640Z/audit.txt
SHA-256: b585617ef2382d51eb86a6fa670c262fb9368cd74a95b08189be7f03d999dbfb
```

The audit exited `0`, reported three warnings and zero failures, and made no configuration, service, listener, route, certificate, firewall, package, or call change.

## Accepted healthy state

- Asterisk `22.10.1` remained active for more than one hour and forty-eight minutes after update.
- Asterisk boot persistence remained enabled.
- Zero active channels, zero active calls and zero processed calls were observed.
- Kamailio retained public, WireGuard and loopback ownership of SIP port `5060`.
- Asterisk retained loopback UDP `127.0.0.1:5061` ownership.
- Asterisk HTTP remained loopback-only on `127.0.0.1:8088`.
- Asterisk HTTPS remained wildcard-bound on `8089`.

## Firewall classification for 8089

The authoritative `inet wwcxfw` input base chain has policy `drop` and permits only:

- loopback traffic;
- established and related traffic;
- ICMP and ICMPv6;
- all traffic entering through `wg0`;
- WireGuard UDP `51820`;
- public TCP `80` and `443`.

New public-interface connections to TCP `8089` therefore fall through to the terminal default-drop path. The separate iptables-nft compatibility chain has policy `accept`, but an accept verdict there does not override a drop verdict in another input base chain. Port `8089` is consequently classified as:

- reachable from loopback;
- reachable from authenticated WireGuard peers because `iifname "wg0" accept` is broad;
- not permitted for new public-interface connections by the observed `wwcxfw` policy.

This closes the immediate public-exposure concern. It does not establish whether every WireGuard peer should be allowed to reach Asterisk `/metrics`, `/media` and `/ws`; that remains a least-privilege hardening decision.

## Confirmed PJSIP configuration defect

The real unresolved issue is the transport definition and runtime registry:

```text
/etc/asterisk/pjsip.conf
  -> includes pjsip.transports.conf

/etc/asterisk/pjsip.transports.conf
  -> first includes pjsip.transports_custom.conf
  -> later defines [0.0.0.0-udp] at 0.0.0.0:5060

/etc/asterisk/pjsip.transports_custom.conf
  -> defines the same [0.0.0.0-udp] name at 127.0.0.1:5061
```

The duplicate name is therefore parsed in a deterministic order: the custom definition appears before the generated definition. Kamailio already owns `5060`, while Asterisk owns `127.0.0.1:5061`. Despite the listener, `pjsip show transports` returns no objects and `pjsip show transport 0.0.0.0-udp` cannot find the object. No PJSIP Sorcery or realtime mapping explains the discrepancy.

Do not edit the generated `pjsip.transports.conf` file. Before any repair, inspect sanitized startup and module-load diagnostics to confirm whether the generated definition failed to bind, the duplicate category was rejected, or the runtime registry entered a partial state.

## Secondary observations

- The reported PJSIP user-agent string still contains `22.8.2`, even though the running binary is `22.10.1`. This appears to be stale generated metadata, not the executable version.
- The TLS certificate remains self-signed and lacks a subject alternative name. This is acceptable only for explicitly trusted internal use and is not a generally trusted public certificate.
- No actual reverse proxy or application consumer of `8089` was established; the focused matches were repository documentation and audit tooling.

## Decision boundary

Accepted:

- current Asterisk health and boot persistence;
- internal-only effective network scope for `8089` under the observed firewall policy;
- continued loopback Asterisk SIP ownership on `5061`;
- continued offline-only alerting laboratory state.

Not yet authorized or performed:

- Asterisk reload or restart;
- PJSIP transport-file edits;
- FreePBX database or generated-configuration changes;
- firewall or WireGuard policy changes;
- certificate replacement;
- endpoint, CAP-feed, Actual-alert, page, call or attention-tone activation.
