# Edge1 Iceland Time Source Live Evidence — 2026-08-17

## Purpose

Record live Edge1 measurements from the bounded Iceland time-source discovery work and preserve the decision boundary before any production chrony change.

Probe implementation merged in PR #338 as `6eb0a1f511091d0a58019a81a4d84ebab3b0b728`.

## First attended Edge1 run

Observed at `2026-08-17T01:32:39Z` from Edge1.

Evidence file written on Edge1:

`/tmp/wwcx-edge1-time-source-discovery-20260817T013229Z.json`

No chrony configuration was changed by the discovery run.

## Current chrony state during discovery

At the end of the first run:

- current selected source: `89.17.158.36`, network source;
- Edge1 chrony stratum: 2;
- system time: `0.000123777` seconds fast of NTP time;
- last offset: `+0.000218851` seconds;
- RMS offset: `0.000704287` seconds;
- root delay: `0.004473228` seconds;
- root dispersion: `0.004777798` seconds;
- leap status: `Normal`.

The selected source appeared in `chronyc -n sources -v` as a stratum-1 server. A later reverse lookup identified `89.17.158.36` as `36-158-17-89.xdsl.hringdu.is`. It was not present in the static `/etc/chrony/chrony.conf`, `/etc/chrony/conf.d/wwcx-nts.conf`, or the inspected `/etc/chrony/sources.d` files.

## Direct/local reference inspection

- No `/dev/pps*`, `/dev/ptp*`, `/dev/gps*`, `/dev/ttyACM*`, or `/dev/ttyUSB*` reference-clock device was detected by the probe.
- No direct PPS/PTP/GPS-like reference was exposed to the VPS through the inspected device/gpsd paths.
- Default gateway candidate `89.147.109.1` did not provide a usable NTP response.

This does not prove the hosting provider has no internal reference-clock infrastructure; it establishes only that no directly exposed or explicitly advertised local reference was found by the bounded probe.

## Iceland candidate results — first five-sample run

### `ht-time01.isnic.is`

- reachable: yes;
- live stratum: 1;
- median RTT: `0.840 ms`;
- median measured clock offset: `0.882 ms`;
- packet reference ID: `GNSs`;
- GNSS evidence classification: `documented-reference-plus-live-stratum1`.

The repository discovery metadata records ISNIC documentation describing this stratum-1 service as GNSS-backed using GPS, GLONASS, and Galileo. The live stratum-1 response satisfies the probe's corroboration gate.

### `mh-time01.isnic.is`

- reachable: yes;
- live stratum: 2;
- median RTT: `0.603 ms`;
- median measured clock offset: `0.958 ms`;
- packet reference ID: `193.4.58.77`;
- no direct GNSS classification was asserted for this source.

## Seven-source apples-to-apples comparison

A second attended run measured all five existing reviewed upstreams plus both ISNIC candidates using the same packet probe for 20 rounds over approximately five minutes.

Evidence file on Edge1:

`/tmp/wwcx-time-source-comparison-20260817T014057Z.jsonl`

All seven sources replied successfully in all 20 rounds.

| Source | Success | Stratum | Median RTT ms | Median offset ms | Median root dispersion ms | RefID |
|---|---:|---:|---:|---:|---:|---|
| `mh-time01.isnic.is` | 20/20 | 2 | 0.593 | +0.113 | 0.274 | `193.4.58.77` |
| `ht-time01.isnic.is` | 20/20 | 1 | 0.782 | +0.140 | 0.015 | `GNSs` |
| `time.cloudflare.com` | 20/20 | 3 | 1.567 | -3.172 | 0.175 | `10.145.8.6` |
| `sth1.ntp.se` | 20/20 | 1 | 59.581 | -2.135 | 0.031 | `PPS` |
| `sth2.ntp.se` | 20/20 | 1 | 59.673 | -2.845 | 0.031 | `PPS` |
| `mmo1.ntp.se` | 20/20 | 1 | 60.931 | +2.238 | 0.031 | `PPS` |
| `time.nist.gov` | 20/20 | 1 | 138.547 | +4.293 | 0.488 | `NIST` |

This comparison confirms that `ht-time01.isnic.is` is not merely reachable: it is a consistently sub-millisecond stratum-1 source from Edge1 with very low reported root dispersion and a measured offset much closer to the Edge1 clock than the remote Netnod/NIST sources during this observation window.

## Current selected source versus ISNIC GNSS comparison

Because chrony was selecting `89.17.158.36`, an additional 20-round direct comparison measured that live selected source with the same packet probe against `ht-time01.isnic.is`.

### `89.17.158.36`

- reverse name: `36-158-17-89.xdsl.hringdu.is`;
- success: 20/20;
- live stratum: 1;
- packet reference ID: `PPS`;
- median RTT: `7.5055 ms`;
- median measured offset: `-0.8235 ms`;
- median root dispersion: `3.6545 ms`.

### `ht-time01.isnic.is`

- success: 20/20;
- live stratum: 1;
- packet reference ID: `GNSs`;
- median RTT: `0.7975 ms`;
- median measured offset: `+0.187 ms`;
- median root dispersion: `0.015 ms`.

In this like-for-like sample, the ISNIC stratum-1 source had roughly one tenth the round-trip latency of the selected `89.17.158.36` source and substantially lower reported root dispersion. The selected source remains valid and synchronized; this comparison supports adding ISNIC, not declaring the existing source invalid.

## Decision

The repeated measurements satisfy the discovery runbook's measurement gate for a proposed production addition of `ht-time01.isnic.is`.

Preferred design:

- add `server ht-time01.isnic.is iburst` as one additional upstream;
- do not add `mh-time01.isnic.is` at this stage, avoiding unnecessary concentration on one operator/reference family;
- retain the existing Netnod, NIST, and Cloudflare sources for geographic/operator diversity;
- retain `minsources 3`;
- do not set `prefer` or force selection of the Icelandic source;
- allow chrony to perform its normal source selection and combining algorithms.

Adding this network stratum-1 source does not make Edge1 a stratum-1 server. When Edge1 synchronizes over NTP to a stratum-1 upstream, Edge1 remains stratum 2 and public clients normally remain one stratum below Edge1.

## Production boundary

The measurement objective is complete, but the live chrony change remains a privileged production action.

Before live activation, prepare and validate the focused repository change. Live deployment must be backup-first and reversible, and acceptance must include:

- `chronyc tracking` synchronized with `Leap status: Normal`;
- `chronyc sources -v` showing the ISNIC source reachable/selectable;
- `chronyc sourcestats -v` showing stable samples;
- existing source diversity preserved;
- `minsources 3` preserved;
- public UDP/123 regression test passes;
- NTS TCP/4460/TLS/ALPN and authenticated-exchange acceptance remain unaffected;
- no DNS or firewall change is required for adding an outbound upstream source.
