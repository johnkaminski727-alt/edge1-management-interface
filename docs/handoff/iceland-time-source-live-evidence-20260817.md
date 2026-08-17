# Edge1 Iceland Time Source Live Evidence — 2026-08-17

## Purpose

Record the first live Edge1 run of the bounded Iceland time-source discovery probe and preserve the decision boundary before any production chrony change.

Probe implementation merged in PR #338 as `6eb0a1f511091d0a58019a81a4d84ebab3b0b728`.

## Attended Edge1 run

Observed at `2026-08-17T01:32:39Z` from Edge1.

Evidence file written on Edge1:

`/tmp/wwcx-edge1-time-source-discovery-20260817T013229Z.json`

No chrony configuration was changed by the discovery run.

## Current chrony state

At the end of the run:

- current selected source: `89.17.158.36`, network source;
- Edge1 chrony stratum: 2;
- system time: `0.000123777` seconds fast of NTP time;
- last offset: `+0.000218851` seconds;
- RMS offset: `0.000704287` seconds;
- root delay: `0.004473228` seconds;
- root dispersion: `0.004777798` seconds;
- leap status: `Normal`.

The selected source appeared in `chronyc -n sources -v` as a stratum-1 server with current sample `+3062us[+3281us] +/- 9684us`.

## Direct/local reference inspection

- No `/dev/pps*`, `/dev/ptp*`, `/dev/gps*`, `/dev/ttyACM*`, or `/dev/ttyUSB*` reference-clock device was detected by the probe.
- No direct PPS/PTP/GPS-like reference was exposed to the VPS through the inspected device/gpsd paths.
- Default gateway candidate `89.147.109.1` did not provide a usable NTP response.

This does not prove the hosting provider has no internal reference-clock infrastructure; it establishes only that no directly exposed or explicitly advertised local reference was found by the bounded probe.

## Iceland candidate results

### `ht-time01.isnic.is`

First live five-sample discovery summary:

- reachable: yes;
- live stratum: 1;
- median RTT: `0.840 ms`;
- median measured clock offset: `0.882 ms`;
- packet reference ID: `GNSs`;
- GNSS evidence classification: `documented-reference-plus-live-stratum1`.

The repository discovery metadata records ISNIC documentation describing this stratum-1 service as GNSS-backed using GPS, GLONASS, and Galileo. The live stratum-1 response satisfies the probe's corroboration gate.

### `mh-time01.isnic.is`

First live five-sample discovery summary:

- reachable: yes;
- live stratum: 2;
- median RTT: `0.603 ms`;
- median measured clock offset: `0.958 ms`;
- packet reference ID: `193.4.58.77`;
- no direct GNSS classification was asserted for this source.

## Interpretation

`ht-time01.isnic.is` is a strong candidate for an additional Edge1 upstream because it is a live stratum-1 source, has documented GNSS reference history, and showed sub-millisecond round-trip latency from Edge1 in the first probe.

The result is promising but not yet sufficient by itself to justify production selection changes. The initial five samples were a short bounded probe; production source selection should be based on repeated observations over time and an apples-to-apples comparison against the existing configured sources.

Adding this network stratum-1 source would not make Edge1 a stratum-1 server. When synchronized over NTP to a stratum-1 upstream, Edge1 normally remains stratum 2 and public clients remain one stratum below Edge1.

## Next safe measurement

Before a production chrony change:

1. collect repeated observations of `ht-time01.isnic.is` over several minutes;
2. measure the existing configured sources with the same packet probe so RTT, offset, and dispersion are directly comparable;
3. inspect the complete JSON evidence, including root dispersion and individual sample stability;
4. retain existing source diversity and `minsources 3` in any proposed production change.

## Production boundary

No production chrony source change is authorized by this evidence record.

If repeated measurements confirm the result, the preferred change is to add `ht-time01.isnic.is` as an additional upstream rather than replace the existing diverse source set. The change should be backup-first, reversible, validated with `chronyc tracking`, `sources -v`, `sourcestats -v`, public NTP regression checks, and NTS regression checks.
