# Control Surfaces passive diagnostic fallbacks

Date: 2026-08-18
Status: repository repair pending CI/live acceptance

## Live root cause

Fresh read-only production evidence showed that the Edge1 Operations API runs as `wwadmin` with `NoNewPrivileges=yes`.

The native component diagnostic commands are intentionally not usable from that account:

- Asterisk control socket: owned by `asterisk:asterisk`, mode `0700`; native `asterisk -rx ...` calls fail to connect.
- Kamailio control socket: native `kamcmd` calls fail with permission denied.
- FreePBX: `fwconsole` is not available in the Operations API execution path.

At the same time, the existing bounded telephony status broker reported the overall telephony stack healthy, Asterisk healthy, zero active calls, zero critical alerts, and no evidence of a service outage.

## Decision

Do not widen the Operations API account, add it to telephony service groups, grant sudo, relax control-socket permissions, or weaken `NoNewPrivileges` merely to make a dashboard card green.

Instead, native CLI diagnostics remain the preferred high-detail path when they are already permitted. If every native check is privilege-gated or unavailable, the diagnostic action runs a fixed passive fallback and reports `limited` when that fallback succeeds.

The fixed fallbacks are:

- Asterisk: process-presence plus loopback SIP listener `5061`; loopback HTTP listeners `8088/8089` are recorded as additional evidence.
- Kamailio: process-presence plus both loopback and non-loopback SIP `5060` listener evidence.
- FreePBX: fixed loopback HTTPS probes for `/admin/` and `/ucp/` using the existing private Apache policy.

These fallbacks accept no caller parameters, arbitrary command, URL, host, port, path, shell fragment, sudo request, AMI/ARI action, database query, or mutation.

## Status semantics

- `ok`: all requested native CLI checks succeeded.
- `limited`: native CLI detail is unavailable/privilege-gated, but the fixed passive health fallback succeeded; or some native checks succeeded while others did not.
- `error` / `unavailable`: native checks failed/unavailable and the passive fallback did not establish the expected component health.

The response includes `native_cli_status` and `passive_fallback` so the interface does not conceal why the result is limited.

## Safety boundary

This repair changes diagnostic interpretation only. It does not change system users/groups, sudoers, file/socket ownership or mode, systemd hardening, firewall, DNS, SIP routing, Asterisk/Kamailio configuration, certificates, calls, messages, or listeners.
