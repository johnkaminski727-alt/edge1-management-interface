# WW.CX Public NTP Service Live Acceptance — 2026-08-15

## Status

**Accepted — publicly reachable over IPv4 UDP/123.**

This record closes the initial WW.CX public NTP deployment objective for `ntp.ww.cx` and its alternate name `time.ww.cx` on Edge1.

## Outside-in acceptance evidence

At approximately 2026-08-15 21:24 UTC, the operator disabled the Edge1 WireGuard connection on a Windows workstation and performed ordinary Windows Time strip-chart queries from the non-WireGuard network path.

### Canonical service name

Command:

```powershell
w32tm /stripchart /computer:ntp.ww.cx /samples:5 /dataonly
```

Observed:

- hostname resolved to `89.147.109.253:123`;
- five consecutive NTP samples were received;
- observed offsets were approximately `+1.447` to `+1.451` seconds relative to the Windows workstation clock.

### Alternate service name

Command:

```powershell
w32tm /stripchart /computer:time.ww.cx /samples:5 /dataonly
```

Observed:

- hostname resolved to `89.147.109.253:123`;
- five consecutive NTP samples were received;
- observed offsets were approximately `+1.447` to `+1.456` seconds relative to the Windows workstation clock.

The successful replies after WireGuard was disabled provide the required outside-in evidence that Internet-side NTP requests reach the Edge1 service on UDP/123 for both public names.

## Previously accepted Edge1 state

Immediately before the outside-in test, attended production evidence had already established:

- `chronyd` active and synchronized;
- leap status `Normal`;
- synchronized stratum 4 operation;
- local packet-level NTP smoke test passing;
- `chronyd` bound to `0.0.0.0:123` and `[::]:123`;
- live `inet wwcxfw input` rule `ip daddr 89.147.109.253 udp dport 123 accept comment "wwcx:public-ntp-v4"`;
- the same IPv4 UDP/123 rule persisted in `/etc/nftables.conf`;
- DNS for `ntp.ww.cx` and `time.ww.cx` pointed to `89.147.109.253`;
- runtime Big Bird firewall controls were preserved by avoiding a full nftables reload;
- rollback evidence stored at `/var/lib/wwcx-deployment-evidence/public-ntp-server/firewall-20260815T211902Z`.

## Acceptance conclusion

The first production phase of the WW.CX NTP service is complete:

- canonical endpoint: `ntp.ww.cx`;
- alternate endpoint: `time.ww.cx`;
- protocol: NTPv4-compatible UDP/123;
- address family accepted: IPv4;
- public IPv4 address: `89.147.109.253`;
- server: Edge1 / `chronyd`;
- outside-in reachability: verified;
- synchronized service response: previously verified locally and continuously by chronyd health evidence.

## Deferred follow-up

Not part of this acceptance:

- public IPv6 NTP / AAAA publication;
- Network Time Security (NTS) / TCP 4460;
- certificate lifecycle for NTS;
- second independent external observer or recurring external NTP monitoring.

Those are follow-up enhancements, not blockers for the accepted IPv4 NTP service.
