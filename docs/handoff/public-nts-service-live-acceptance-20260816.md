# WW.CX Public NTS Service Live Acceptance — 2026-08-16

## Status

**Accepted — publicly reachable and authenticated over IPv4 NTS.**

This record closes the initial Network Time Security acceptance objective for the canonical WW.CX time hostname `ntp.ww.cx`.

## Edge1 production state already accepted

The attended 2026-08-15 Edge1 rollout established:

- a dedicated Let's Encrypt ECDSA certificate for `ntp.ww.cx`;
- chronyd NTS-KE on TCP/4460 with ALPN `ntske/1`;
- standard NTP preserved on UDP/123;
- live and persistent IPv4 firewall publication for `89.147.109.253:4460/tcp`;
- a lineage-specific Certbot deploy hook for chronyd credential refresh;
- controlled renewal-hook restage/restart validation;
- rollback evidence for certificate, NTS activation, firewall publication, renewal-hook installation, and renewal lifecycle validation.

See:

```text
docs/handoff/nts-edge1-live-activation-20260815.md
```

## Independent Internet-side NTS-KE verification

A disposable GitHub-hosted Ubuntu 24.04 runner in Azure East US was used as an independent external network on 2026-08-16.

Workflow run:

```text
31916364482
```

The runner resolved:

```text
ntp.ww.cx -> 89.147.109.253
```

The repository NTS-KE probe then connected to `ntp.ww.cx:4460` and reported:

```text
reachable:                 true
tls_verified:              true
alpn:                      ntske/1
resolved_address:          89.147.109.253
certificate_not_after_utc: 2026-11-13T22:54:08Z
rtt_ms:                    319.934
```

This proves Internet-side TCP/4460 reachability, public certificate validation, hostname validation, and NTS-KE ALPN negotiation from a network independent of Edge1.

## Authenticated NTS time exchange

The same disposable external runner used chronyd 4.5 with `+NTS` support.

The client was intentionally run with `/dev/null` as its configuration file so no default/public pool sources could satisfy the test. Its only configured time source was:

```text
server ntp.ww.cx iburst nts maxsamples 1
```

The measurement command used chronyd `-Q`, so the runner system clock was not changed.

Observed result:

```text
chronyd version 4.5 starting (... +NTS ...)
Disabled control of system clock
System clock wrong by -0.004066 seconds (ignored)
chronyd exiting
```

The command exited successfully and the workflow emitted:

```text
WW.CX external NTS-KE verification: PASS
WW.CX authenticated NTS time exchange: PASS
```

Because the only configured source required the `nts` directive, this is the required completed authenticated NTS time exchange from outside Edge1.

## Business159 observer path limitation

Business159 remains the accepted recurring outside observer for standard NTP and the public web-clock anchor.

At `2026-08-16T00:00:54Z`, Business159 still received valid standard NTP from `89.147.109.253` at stratum 4, but its TCP/4460 NTS-KE connection returned an immediate connection refusal before TLS negotiation.

The Business159 observer therefore correctly kept:

```text
NTS expected flag: 0
```

and did not advertise NTS as healthy from that observer.

A subsequent read-only Edge1 diagnostic established simultaneously that:

- chronyd remained active;
- chronyd was listening on `0.0.0.0:4460` and `[::]:4460`;
- the live and persistent `wwcx:public-nts-ke-v4` firewall rule remained present;
- `89.147.109.253` is directly assigned to Edge1 `ens3`;
- the repository local NTS smoke test passed;
- TLS/certificate/ALPN verification succeeded over `127.0.0.1:4460`;
- TLS/certificate/ALPN verification also succeeded from Edge1 to its own public IPv4 `89.147.109.253:4460`.

The independent GitHub-hosted authenticated NTS exchange then proved the public service from another Internet source. Therefore the Business159 refusal is a path-specific observer limitation, not evidence that WW.CX NTS is unavailable generally.

Do not set Business159 `WWCX_NTS_EXPECTED=1` while its hosting network cannot successfully reach TCP/4460; doing so would intentionally make its fail-closed observer report an error.

## Acceptance conclusion

The initial WW.CX public time service now has these accepted production capabilities:

- canonical hostname: `ntp.ww.cx`;
- alternate standard-NTP hostname: `time.ww.cx`;
- standard NTP: IPv4 UDP/123, accepted and recurring-observed from Business159;
- NTS-KE: IPv4 TCP/4460, publicly reachable from an independent external network;
- NTS certificate validation: accepted;
- NTS ALPN `ntske/1`: accepted;
- authenticated NTS time exchange: accepted from an independent external chrony client;
- certificate renewal lifecycle: installed and live-validated;
- standard NTP regression after NTS activation: accepted;
- public IPv6 NTP/NTS: still deferred.

## Remaining observer/web follow-up

The service itself is accepted. Remaining convenience work is observer presentation, not NTS service activation:

1. keep Business159's five-minute standard-NTP observer active;
2. keep Business159 NTS expectation disabled until its TCP/4460 path is resolved or the public status schema is updated to distinguish service acceptance from Business159-specific NTS reachability;
3. update the WW.CX and CreekCo public pages so they can truthfully present NTS as externally authenticated while separately disclosing Business159's current TCP/4460 observer limitation;
4. optionally investigate the Business159 path with a simultaneous Edge1 packet capture and Business159 connection attempt or with the hosting provider.

No claim of legal metrology, guaranteed accuracy, or public IPv6 support is made by this acceptance.
