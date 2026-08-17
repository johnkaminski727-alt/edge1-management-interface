# Edge1 ISNIC GNSS Upstream Live Acceptance — 2026-08-17

## Result

**PASS.** `ht-time01.isnic.is` is live as an additional production chrony upstream on Edge1.

The guarded production installer completed successfully on 2026-08-17 at approximately 02:13 UTC and selected the ISNIC stratum-1 source without changing DNS, firewall, certificate, or NTS configuration.

## Authorization boundary

The authorized production action was limited to:

- add `ht-time01.isnic.is` as an additional Edge1 chrony upstream;
- restart chrony;
- run the guarded NTP/NTS validation with automatic rollback on failure.

DNS, firewall, and certificate changes were explicitly outside scope and were not performed.

## Reviewed repository state

The rollout package was merged by PR #340 at:

`82f79d4b560fc001f66d6754d8d903e334ddc1e1`

The live Edge1 checkout fast-forwarded `main` to:

`1c115663fb23de82e51fcfd0520d91fa196261be`

The reviewed rollout merge was verified as an ancestor before activation.

Pre-deploy validation passed:

- `tests/validate_time_authority_isnic_upstream.py`;
- `tests/validate_time_authority_ntp_server.py`.

## Pre-change state

Immediately before activation:

- selected source: `89.17.158.36` / `36-158-17-89.xdsl.hringdu.is`;
- Edge1 stratum: 2;
- system time: `0.000002335` seconds fast of NTP time;
- last offset: `+0.000008379` seconds;
- RMS offset: `0.000371804` seconds;
- root delay: `0.003472190` seconds;
- root dispersion: `0.004897033` seconds;
- leap status: `Normal`.

The five reviewed static upstreams were all reachable:

- `sth1.ntp.se`;
- `sth2.ntp.se`;
- `mmo1.ntp.se`;
- `time.nist.gov`;
- `time.cloudflare.com`.

`89.17.158.36` had previously been observed as a live selected source but was not present in the inspected persistent chrony configuration. It therefore did not survive the intentional chrony restart. This is recorded as expected runtime-state loss, not removal of a reviewed static source.

## Live preflight

Immediately before installing the fragment, the guarded installer independently probed `ht-time01.isnic.is` and received:

- resolved address: `193.4.58.77`;
- stratum: 1;
- RTT: `0.785 ms`;
- measured offset: `+0.286 ms`;
- root dispersion: `0.015 ms`.

The preflight passed the required synchronized-stratum-1 gate.

## Installed production fragment

Path:

`/etc/chrony/conf.d/wwcx-isnic-upstream.conf`

Effective source directive:

```text
server ht-time01.isnic.is iburst
```

No `prefer` directive is used.

## Post-change chrony acceptance

Immediately after the guarded restart and synchronization wait:

- reference: `ht-time01.isnic.is`;
- reference ID: `C1043A4D`;
- Edge1 stratum: 2;
- system time: `0.000000013` seconds fast of NTP time;
- last offset: `-0.000035204` seconds;
- RMS offset: `0.000035204` seconds;
- root delay: `0.000739341` seconds;
- root dispersion: `0.000074467` seconds;
- leap status: `Normal`.

Chrony selected the new source:

```text
^* ht-time01.isnic.is  1  6  17  3  +3386ns[ -32us] +/- 387us
```

Initial post-restart source statistics for ISNIC:

- samples: 4;
- residual runs: 4;
- span: 6 seconds;
- estimated offset: `-43 us`;
- standard deviation: `7.806 us`.

These source statistics were captured only seconds after restart and are therefore an initial acceptance snapshot, not a long-window stability estimate.

## Diversity preserved

The reviewed independent upstream set remained present after restart:

- Netnod Stockholm source 1;
- Netnod Stockholm source 2;
- Netnod Malmö source;
- NIST;
- Cloudflare;
- ISNIC `ht-time01.isnic.is`.

`minsources 3` remains part of the base configuration and the ISNIC fragment does not force source selection.

## Public NTP/NTS regression acceptance

The guarded installer completed its post-change acceptance sequence successfully, including:

- chrony active after restart;
- synchronized state with `Leap status: Normal`;
- ISNIC source present;
- public UDP/123 listener present;
- existing public NTP local smoke test passed;
- NTS-KE TCP/4460 listener present;
- local TLS negotiation with ALPN `ntske/1` passed.

Listener inspection after activation showed chronyd listening on:

- IPv4 UDP/123;
- IPv6 UDP/123;
- IPv4 TCP/4460;
- IPv6 TCP/4460.

This listener state does not change the existing policy that public IPv6 NTP/NTS publication is deferred; no IPv6 firewall or DNS publication was added by this rollout.

## Evidence

Installer evidence root on Edge1:

`/var/lib/wwcx-deployment-evidence/public-ntp-server/isnic-upstream-20260817T021320Z`

The installer preserved before/after chrony state, listener state, the direct ISNIC preflight record, the reviewed fragment, public-NTP smoke output, and local NTS TLS/ALPN output under that evidence directory.

## Acceptance conclusion

The production objective is complete:

- GNSS-backed ISNIC stratum-1 upstream added;
- Edge1 remains correctly stratum 2;
- ISNIC was selected by chrony without `prefer`;
- timing metrics improved materially in the immediate post-change snapshot;
- reviewed independent upstream diversity remains available;
- public NTP and NTS listeners/acceptance checks passed;
- no DNS, firewall, or certificate changes were made;
- no rollback was triggered.

A later long-window observation may be useful for trend analysis, but it is not a blocker for this production acceptance.
