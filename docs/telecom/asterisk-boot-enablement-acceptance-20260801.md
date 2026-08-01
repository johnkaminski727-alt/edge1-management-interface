# Asterisk Boot Enablement Acceptance — 2026-08-01

## Execution

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

Evidence directory:

```text
/var/lib/wwcx-deployment-evidence/asterisk-boot-enablement/20260801T010843Z
```

## Accepted result

Asterisk startup was enabled through the existing SysV-backed service integration without restarting the running PBX.

- host: `edge1.ww.cx`;
- Asterisk PID before and after: `1651722`;
- service state after change: `active`;
- boot state after change: `enabled`;
- rollback was not required;
- no active-call interruption was reported;
- no Asterisk, Kamailio, SIP, CAP, alerting, firewall, listener, route, certificate, or dialplan configuration changed.

## Verified startup links

```text
/etc/rc0.d/K01asterisk -> ../init.d/asterisk
/etc/rc1.d/K01asterisk -> ../init.d/asterisk
/etc/rc2.d/S01asterisk -> ../init.d/asterisk
/etc/rc3.d/S01asterisk -> ../init.d/asterisk
/etc/rc4.d/S01asterisk -> ../init.d/asterisk
/etc/rc5.d/S01asterisk -> ../init.d/asterisk
/etc/rc6.d/K01asterisk -> ../init.d/asterisk
```

This is the expected SysV policy: stop links for shutdown/single-user runlevels and start links for normal multi-user runlevels.

## Remaining alerting and telephony gates

1. Reconcile why `pjsip show transports` reports no objects while Asterisk owns UDP `127.0.0.1:5061` and duplicate transport section names exist across generated and custom files.
2. Determine the intended consumers and permitted network scope for Asterisk HTTPS/WebSocket port `8089`.
3. Replace or appropriately trust the self-signed `edge1.ww.cx` certificate only within an approved certificate and listener plan.
4. Keep CAP feeds, `Actual` alerts, calls/pages, attention-tone transmission, and public certification claims blocked pending separate authority and conformance evidence.

## Acceptance boundary

Accepted: Asterisk boot persistence through the existing service mechanism.

Not tested: a real host reboot. Reboot validation remains a separately scheduled operational test because it affects all services on Edge1.
