# WW.CX NTP listener-check incident — 2026-08-15

## Summary

During the first attended Edge1 chrony cutover, the actual local NTP packet smoke test succeeded against `127.0.0.1:123`, `chronyc tracking` reported a synchronized normal leap state, and `chronyc sources -v` selected a valid upstream. The installer nevertheless ended with `FAIL: chronyd is not listening on UDP/123`.

The failure was a validation false negative, not an NTP service failure. The shell check parsed a positional field from `ss -lun` output with `awk '{print $5}'`. The column layout is not a stable contract for this purpose and did not identify the local UDP/123 socket on the live Debian host.

## Correction

Both the preflight and installer now use the native iproute2 socket filter:

```sh
ss -H -lun 'sport = :123'
```

The deployment validator requires the native filter and rejects the old positional parser.

## Live evidence from the attended run

Accepted observations before the false-negative assertion:

- chrony package installed and systemd-timesyncd package removed by the package transition;
- local NTPv4 request to `127.0.0.1:123` received a valid mode-4 response;
- observed local server stratum was 4;
- leap indicator was synchronized/normal;
- `chronyc tracking` reported `Leap status: Normal`;
- `time.cloudflare.com` was the selected source at the observed instant;
- all five configured upstreams were present in `chronyc sources -v`.

A follow-up run with the corrected socket filter conclusively observed chronyd listening on both wildcard address families:

```text
0.0.0.0:123
[::]:123
```

The same follow-up showed `chrony.service` active while the non-root `wwadmin` invocation `chronyc tracking` returned `506 Cannot talk to daemon`. This is a local control-socket privilege boundary, not evidence that NTP service traffic is unavailable. The reviewed configuration disables the remote chronyc UDP command port (`cmdport 0`); operational chronyc inspection on Edge1 should therefore use `sudo chronyc ...` through the local Unix-domain control socket. Do not weaken socket permissions merely to make unprivileged chronyc commands convenient.

This record does not claim public Internet reachability. Firewall publication and external UDP/123 acceptance remain separate evidence requirements.
