# Edge1 ISNIC GNSS Upstream Rollout — 2026-08-17

## Objective

Add `ht-time01.isnic.is` as one additional chrony upstream on Edge1 after repeated live measurements showed it to be a stable, sub-millisecond, stratum-1 GNSS-backed source from Iceland.

This rollout intentionally preserves the existing Netnod, NIST, and Cloudflare sources, retains `minsources 3`, and does not use `prefer`.

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

## Production boundary

Preparing and merging this package does not activate the source on Edge1.

Live activation is a privileged production clock-service change and requires explicit authorization for this exact action. After authorization, run from the reviewed `main` revision:

```sh
cd /opt/edge1-management-interface
sudo env WWCX_TIME_APPROVE_ISNIC_UPSTREAM=YES \
  sh deploy/install-time-authority-isnic-upstream-edge1.sh
```

## Live acceptance

After activation, preserve the installer evidence and additionally inspect:

```sh
sudo chronyc tracking
sudo chronyc -N sources -v
sudo chronyc -N sourcestats -v
```

Acceptance requires a synchronized Edge1 clock, the ISNIC source reachable/selectable, existing independent sources still present, and no regression of public NTP or NTS service.

Do not claim that Edge1 is stratum 1 merely because it uses a stratum-1 network upstream. Edge1 remains downstream of the reference and normally serves as stratum 2 when synchronized to a stratum-1 source.
