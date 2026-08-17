# Edge1 ISNIC GNSS Upstream Rollout — 2026-08-17

## Objective

Add `ht-time01.isnic.is` as one additional chrony upstream on Edge1 after repeated live measurements showed it to be a stable, sub-millisecond, stratum-1 GNSS-backed source from Iceland.

This rollout intentionally preserves the existing Netnod, NIST, and Cloudflare sources, retains `minsources 3`, and does not use `prefer`.

## Status

**LIVE / ACCEPTED — 2026-08-17.**

The production activation completed successfully. The authoritative live acceptance record is:

`docs/handoff/isnic-gnss-upstream-live-acceptance-20260817.md`

Installer evidence root on Edge1:

`/var/lib/wwcx-deployment-evidence/public-ntp-server/isnic-upstream-20260817T021320Z`

## Measurement basis

The accepted measurement record is:

`docs/handoff/iceland-time-source-live-evidence-20260817.md`

Key repeated results:

- `ht-time01.isnic.is`: 20/20, stratum 1, `0.782 ms` median RTT, `+0.140 ms` median offset, `0.015 ms` median root dispersion, RefID `GNSs`;
- direct comparison against chrony's selected `89.17.158.36`: ISNIC `0.7975 ms` median RTT and `0.015 ms` dispersion versus `7.5055 ms` and `3.6545 ms` respectively;
- no directly exposed PPS/PTP/GPS device was found on the VPS;
- no usable NTP service was found on the default gateway.

## Repository assets

- `modules/time-authority/config/wwcx-isnic-upstream.conf`
- `deploy/install-time-authority-isnic-upstream-edge1.sh`
- `tests/validate_time_authority_isnic_upstream.py`
- `.github/workflows/time-authority-isnic-upstream-validation.yml`

The guarded rollout package was merged by PR #340 as:

`82f79d4b560fc001f66d6754d8d903e334ddc1e1`

## Design

The production source is installed as a separate chrony fragment:

`/etc/chrony/conf.d/wwcx-isnic-upstream.conf`

The existing base configuration already contains `confdir /etc/chrony/conf.d`, so no base-file rewrite is required.

Reviewed fragment:

```text
server ht-time01.isnic.is iburst
```

Do not add `prefer`. Do not remove existing upstreams as part of this change. Do not add `mh-time01.isnic.is` at this stage.

## Guarded activation

The installer requires explicit live-production approval:

```text
WWCX_TIME_APPROVE_ISNIC_UPSTREAM=YES
```

It then:

1. requires root/sudo and an already healthy `chrony.service`;
2. resolves `ht-time01.isnic.is`;
3. sends a direct standard-NTP preflight probe and requires a synchronized stratum-1 reply;
4. captures pre-change tracking, sources, source statistics, UDP/123 and TCP/4460 listener state;
5. backs up any previous ISNIC fragment;
6. installs only the reviewed fragment;
7. restarts chrony and waits for synchronization;
8. verifies the ISNIC source is present and leap status is Normal;
9. verifies UDP/123 remains listening;
10. verifies TCP/4460 remains listening and negotiates TLS ALPN `ntske/1` locally;
11. runs the existing public-NTP local smoke test;
12. stores evidence under `/var/lib/wwcx-deployment-evidence/public-ntp-server/isnic-upstream-<UTC timestamp>`;
13. automatically restores the previous fragment state and restarts chrony if post-change validation fails.

No DNS, firewall, certificate, or NTS configuration change is performed.

## Live activation result

The authorized activation was executed from Edge1 after verifying the reviewed PR #340 merge was present in the live `main` ancestry.

Fresh installer preflight:

- address: `193.4.58.77`;
- stratum: 1;
- RTT: `0.785 ms`;
- measured offset: `+0.286 ms`;
- root dispersion: `0.015 ms`.

Immediately after restart and synchronization:

- selected reference: `ht-time01.isnic.is`;
- Edge1 stratum: 2;
- system time: `0.000000013` seconds fast of NTP time;
- RMS offset: `0.000035204` seconds;
- root delay: `0.000739341` seconds;
- root dispersion: `0.000074467` seconds;
- leap status: `Normal`;
- initial selected-source estimate: about `-43 us` offset with `7.806 us` standard deviation over the first four samples.

The five reviewed static Netnod/NIST/Cloudflare sources remained present after restart. The previously selected runtime source `89.17.158.36` was not part of the inspected persistent chrony configuration and did not survive the restart; its disappearance is recorded in the live acceptance document rather than treated as removal of a reviewed source.

Public UDP/123 and NTS TCP/4460 remained listening and the installer's public-NTP smoke plus local NTS TLS/ALPN acceptance passed. No rollback was triggered.

## Ongoing operating rule

Do not claim that Edge1 is stratum 1 merely because it uses a stratum-1 network upstream. Edge1 remains downstream of the reference and normally serves as stratum 2 when synchronized to a stratum-1 source.

Retain the independent upstream set and `minsources 3`. Do not introduce `prefer` for ISNIC without a separately measured and reviewed reason.
