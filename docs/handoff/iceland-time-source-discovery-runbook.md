# Edge1 Iceland Time Source Discovery Runbook

## Objective

Measure whether Edge1 can obtain lower-latency, higher-quality time from an Icelandic GNSS-backed reference and determine whether the local host/network already exposes a GPS/GNSS/PPS/PTP or network-advertised NTP source.

This phase is **read-only discovery**. It does not change chrony, the host clock, firewall, DNS, routing, or public NTP/NTS service configuration.

## Current production baseline

Edge1 currently uses these chrony upstreams:

- `sth1.ntp.se`
- `sth2.ntp.se`
- `mmo1.ntp.se`
- `time.nist.gov`
- `time.cloudflare.com`

The production configuration requires `minsources 3`, does not use `local`, and publishes the WW.CX public NTP service separately.

## Iceland candidates

ISNIC currently documents the following direct sources for operators of NTP servers:

- `ht-time01.isnic.is` — stratum 1
- `mh-time01.isnic.is` — stratum 2

ISNIC's description of the replacement stratum-1 clock states that it derives time from GNSS constellations including GPS, GLONASS, and Galileo. The discovery configuration therefore records that reference history, but the probe still requires a live stratum-1 reply before classifying the candidate as `documented-reference-plus-live-stratum1`.

Candidate metadata lives in:

`modules/time-authority/config/iceland-candidate-sources.json`

## Probe behavior

`tools/time_authority/discover_edge1_time_sources.py` performs only bounded read-only checks:

1. captures `chronyc tracking`, `sources -v`, `sourcestats -v`, and `activity`;
2. identifies the currently selected chrony source when possible;
3. checks for local `/dev/pps*`, `/dev/ptp*`, `/dev/gps*`, `/dev/ttyACM*`, and `/dev/ttyUSB*` devices;
4. checks `gpsd.service` and `gpsd.socket` state;
5. extracts NTP server addresses explicitly advertised in readable systemd-networkd, NetworkManager, or dhclient lease data;
6. checks the default gateway as a single local-network NTP candidate;
7. sends five standard NTP client requests to each reviewed Iceland candidate and three to each network-advertised/gateway candidate;
8. records stratum, reference ID, RTT, offset, root dispersion, leap state, and errors;
9. writes JSON evidence when requested.

The probe deliberately **does not sweep the VPS/provider subnet**. Neighbouring public addresses are not assumed to be under WW.CX authority.

A packet reference ID such as `GPS` or `PPS` is treated only as a hint unless corroborated by operator documentation. Stratum 1 alone is also not proof of a particular hardware reference.

## Edge1 attended run

From a clean checkout of `edge1-management-interface` containing this probe:

```sh
sh deploy/time-authority-edge1-source-discovery.sh
```

The wrapper writes JSON evidence under `/tmp/wwcx-edge1-time-source-discovery-<UTC timestamp>.json` and also prints the complete report.

No root privilege is required for the intended checks, although some host inspection fields may report unavailable if the current account cannot read them.

## Evaluation criteria

A candidate is promising when repeated live samples show:

- synchronized replies (`leap_indicator != 3`);
- expected stratum;
- consistently lower RTT than the current selected upstream;
- low and stable clock offset;
- low root dispersion;
- no packet-loss/reachability instability.

For `ht-time01.isnic.is`, a successful stratum-1 live reply plus ISNIC's GNSS documentation is strong evidence that Edge1 can directly use a nearby GNSS-backed source. It is still advisable to collect repeated observations before changing production selection.

## Production-change boundary

Do not modify `/etc/chrony/chrony.conf`, install a new source fragment, or restart chrony based solely on this discovery run.

If the Icelandic source performs materially better, prepare a focused production change that adds it as another upstream while retaining source diversity and `minsources 3`. Review the candidate measurements before applying that change.

## References

- ISNIC current time-server page: `https://www.isnic.is/en/ntp`
- ISNIC GNSS replacement-clock history: `https://www.isnic.is/en/news/view?id=585`
- Network Time Foundation NTP server guidance: `https://support.ntp.org/Servers/`
