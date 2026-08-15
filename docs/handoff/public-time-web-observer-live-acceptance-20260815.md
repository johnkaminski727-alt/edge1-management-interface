# WW.CX Public Time Web and Business159 Observer Live Acceptance — 2026-08-15

## Scope

This record accepts the live public-web and independent-observer portion of the WW.CX Time Authority rollout.

Accepted in this record:

- Business159 independently querying the public Edge1 NTP endpoint over UDP/123;
- five-minute unprivileged observer scheduling on Business159;
- sanitized observer state published outside the website document roots;
- `ww.cx` and `creekco.ca` public time APIs consuming that observer state;
- both public time pages presenting standard NTP as online when the observer is healthy;
- NTS remaining explicitly not expected and not advertised as active.

Not accepted or activated by this record:

- NTS certificate installation;
- chronyd NTS-KE listener activation on TCP/4460;
- public TCP/4460 firewall publication;
- authenticated NTS client acceptance;
- IPv6 NTP/NTS publication.

## Repository state

Edge1 operations repository revision containing the Business159 observer invocation fix:

```text
20c010846dd6469700f41881d0acab8e56834eb9
```

WW.CX website repository revision containing the Business159 PHP account-home status-path fix:

```text
1ee8cf2fd6c338fde47d2241cb0f4065d3220e8a
```

The observer fix changed the installer to invoke its smoke test through `sh`, removing dependence on the source checkout execute bit. The website fix added a safe hosting-account-root fallback for cPanel/LiteSpeed requests where PHP does not inherit `HOME`.

## Business159 live acceptance

Authenticated operator execution on Business159 completed the observer install and smoke test successfully.

Installed paths reported by the installer:

```text
observer root:              /home/wwcxjywl/wwcx-public-time-observer
private measurement history:/home/wwcxjywl/private/wwcx-time-authority/public-service-measurements.jsonl
sanitized public status:    /home/wwcxjywl/shared/wwcx-time-service/public-status.json
```

Installed user cron schedule:

```text
*/5 * * * * WWCX_TIME_AUTHORITY_PYTHON=python3 /home/wwcxjywl/wwcx-public-time-observer/observe-public-time-service.sh >/dev/null 2>&1
```

NTS expectation remained deliberately disabled:

```text
NTS expected flag: 0
```

## Accepted external NTP observation

The first accepted Business159 observation after the installer fix reported:

```text
observed_at_utc:  2026-08-15T22:52:10.480750Z
reachable:        true
resolved_address: 89.147.109.253
stratum:          4
rtt_ms:           39.335
clock_offset_ms:  0.212
leap_indicator:   0
ntp_version:      4
```

This is the required independent outside-Edge1 UDP/123 observation for the standard NTP service. It confirms that `ntp.ww.cx` was not merely listening locally: an independent host received a valid NTPv4 response from the reviewed Edge1 public IPv4 address.

The same observation recorded NTS as intentionally unavailable rather than failed production service:

```text
expected:     false
reachable:    false
tls_verified: false
alpn:         null
```

## Public API acceptance

After deployment of the website account-home fix, both public APIs returned healthy observer-backed state.

Accepted WW.CX result:

```text
ok:              true
clock source:    wwcx-ntp-via-business159
observer:        business159 healthy
ntp reachable:   true
address:         89.147.109.253
stratum:         4
rtt_ms:          39.335
clock_offset_ms: 0.212
nts expected:    false
nts reachable:   false
```

Accepted CreekCo result matched the WW.CX result for observer health and NTP measurement.

A separate public HTTP recheck at `2026-08-15T22:55:02Z` confirmed `https://ww.cx/api/time-status.php` still returned:

```text
ok=true
clock.source=wwcx-ntp-via-business159
observer.status=healthy
observer.stale=false
ntp.reachable=true
ntp.resolved_address=89.147.109.253
ntp.stratum=4
ntp.leap_indicator=0
nts.expected=false
nts.reachable=false
```

## Public page acceptance

Both pages passed direct HTTP presence checks:

```text
https://ww.cx/time/
https://creekco.ca/time/
```

The WW.CX page was separately rechecked after deployment and visibly reported:

- clock anchored to the latest Business159 observation of `ntp.ww.cx`;
- Standard NTP: `ONLINE`;
- Independent observer: `EXTERNAL OBSERVER HEALTHY`;
- endpoint address observed from Business159: `89.147.109.253`;
- NTS state: `NTS UPGRADE PENDING`.

## Acceptance conclusion

The public standard-NTP architecture is accepted live:

```text
Edge1 chronyd
    -> public IPv4 UDP/123
    -> ntp.ww.cx / time.ww.cx
    -> independently queried by Business159
    -> sanitized observer state
    -> WW.CX and CreekCo public time APIs/pages
```

The service is externally observed, not self-certified. The public web clock is now anchored to the Business159 NTP observation when fresh.

## Next gate: NTS

The next safe action is read-only certificate discovery on Edge1:

```bash
sudo tools/time_authority/discover-nts-certificate-edge1.sh
```

If no existing certificate covers `ntp.ww.cx`, certificate issuance remains a separate privileged production action requiring explicit approval. If a suitable certificate exists, run the repository NTS read-only preflight with reviewed certificate and key paths before requesting any activation approval.

NTS activation must remain fail-closed and requires separate explicit approval for:

1. certificate/key installation for chronyd;
2. activation of the chronyd TCP/4460 NTS-KE listener;
3. public firewall publication of TCP/4460.

Full NTS acceptance also requires an authenticated NTS time exchange from outside Edge1; TLS/ALPN reachability alone is insufficient.
