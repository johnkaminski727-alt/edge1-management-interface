# WW.CX Edge1 NTS Live Activation — 2026-08-15

## Status

**Edge1 production activation accepted locally; external authenticated NTS acceptance remains pending.**

This record captures the attended activation of Network Time Security (NTS) for the existing WW.CX public time service on Edge1.

The activation was explicitly authorized for all four privileged production actions:

1. issue a dedicated public certificate for `ntp.ww.cx`;
2. install the certificate/key for chronyd and activate NTS-KE on TCP/4460;
3. publish IPv4 TCP/4460 through the Edge1 firewall;
4. install and exercise the Certbot-to-chronyd renewal deploy hook.

This record does **not** claim final Internet-side NTS acceptance. A full authenticated NTS time exchange from outside Edge1 remains required.

## Deployment revision

The attended rollout updated the Edge1 checkout to:

```text
40004fdb4ab034c0ae3051be69df8c83e9db7f61
```

The reviewed NTS certificate lifecycle merge `016cd733342e4c11043f6f911f6143c1346e3442` was verified as an ancestor before production mutation.

## Pre-change NTP baseline

Immediately before NTS activation:

- `chrony.service` was active;
- selected source was `time.cloudflare.com`;
- server stratum was 4;
- leap status was `Normal`;
- system-time error was approximately 0.124 ms;
- the local packet-level NTP smoke test passed.

Standard NTP therefore entered the NTS rollout from an accepted healthy state.

## Dedicated `ntp.ww.cx` certificate

Certbot successfully created a dedicated ECDSA lineage:

```text
/etc/letsencrypt/live/ntp.ww.cx/fullchain.pem
/etc/letsencrypt/live/ntp.ww.cx/privkey.pem
```

Public certificate metadata observed during acceptance:

```text
subject:   CN = ntp.ww.cx
issuer:    Let's Encrypt YE1
notBefore: 2026-08-15 22:54:09 UTC
notAfter:  2026-11-13 22:54:08 UTC
SAN:       DNS:ntp.ww.cx
```

The lineage is separate from the existing Edge1, interconnect, portal and VPN certificate lineages. Certbot reported that its scheduled renewal mechanism will update the lineage.

The guarded NTS preflight then passed with the new certificate and matching private key while TCP/4460 was still free.

## Local NTS-KE activation

The reviewed installer staged the certificate/key under chronyd's NTS credential directory and activated NTS-KE.

Accepted listeners after activation:

```text
0.0.0.0:123/udp   chronyd
[::]:123/udp      chronyd
0.0.0.0:4460/tcp  chronyd
[::]:4460/tcp     chronyd
```

Local NTS-KE TLS verification succeeded with:

```text
SNI:  ntp.ww.cx
ALPN: ntske/1
peer: 127.0.0.1:4460
```

The standard UDP/123 packet smoke test and the NTS local smoke test both passed after the chronyd restart. Leap status remained `Normal` and the service remained stratum 4.

Activation rollback evidence:

```text
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-20260815T235243Z
```

## Public IPv4 TCP/4460 firewall publication

The guarded firewall publisher installed the reviewed NTS-KE rule without reloading the complete nftables ruleset.

Accepted live rule:

```text
ip daddr 89.147.109.253 tcp dport 4460 accept comment "wwcx:public-nts-ke-v4"
```

The live input chain showed the NTS rule immediately after the existing public NTP UDP/123 rule and before the public-web and Big Bird policy-log rules.

The same rule was persisted in `/etc/nftables.conf` between the existing UDP/123 and public-web rules.

The expected iptables-nft / MASQUERADE warnings occurred during nft syntax processing and were non-fatal, matching the previously understood Edge1 mixed nftables environment.

The helper explicitly left public IPv6 NTS unchanged and intentionally did not reload `nftables.service`, preserving runtime Big Bird controls.

Firewall rollback evidence:

```text
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-firewall-20260815T235250Z
```

## Certificate renewal lifecycle

The reviewed lineage-scoped Certbot deploy hook was installed at:

```text
/etc/letsencrypt/renewal-hooks/deploy/50-wwcx-ntp-chrony-nts
```

Accepted metadata:

```text
owner: root:root
mode:  0755
```

The installer confirmed unrelated certificate lineages are ignored.

A controlled live validation was then performed against the current `ntp.ww.cx` lineage. The hook:

- restaged the certificate/key into chronyd's NTS credential directory;
- restarted chronyd;
- waited for synchronization to return;
- revalidated UDP/123;
- revalidated TCP/4460 ownership;
- revalidated trusted TLS plus ALPN `ntske/1`;
- preserved rollback evidence.

The controlled lifecycle test completed successfully and reported:

```text
WW.CX chronyd NTS credentials refreshed from Certbot lineage /etc/letsencrypt/live/ntp.ww.cx.
Standard NTP and local NTS-KE checks passed.
```

Renewal evidence:

```text
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-renewal-hook-20260815T235251Z
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-renewal-20260815T235251Z
```

## Post-lifecycle acceptance

After the controlled renewal-hook restart:

- `chrony.service` was active;
- selected source remained `time.cloudflare.com`;
- stratum remained 4;
- leap status remained `Normal`;
- UDP/123 was owned by chronyd on IPv4 and IPv6 listeners;
- TCP/4460 was owned by chronyd on IPv4 and IPv6 listeners;
- standard NTP packet smoke passed;
- local NTS-KE TLS/ALPN smoke passed;
- Certbot listed the dedicated `ntp.ww.cx` certificate as valid for 89 days;
- the live IPv4 firewall contained both `wwcx:public-ntp-v4` and `wwcx:public-nts-ke-v4` before public web/policy processing.

## Evidence inventory

The accepted rollout created these evidence directories:

```text
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-certificate-20260815T235227Z
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-20260815T235243Z
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-firewall-20260815T235250Z
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-renewal-hook-20260815T235251Z
/var/lib/wwcx-deployment-evidence/public-ntp-server/nts-renewal-20260815T235251Z
```

No private-key contents are recorded in this repository acceptance document.

## Remaining external acceptance gate

Edge1-side NTS production activation is complete, but NTS must not yet be called fully accepted from the local TLS check alone.

Remaining acceptance sequence:

1. run the Business159 observer from outside Edge1 and verify trusted certificate + ALPN `ntske/1` on TCP/4460;
2. perform a full authenticated NTS client time exchange from a host outside Edge1, preferably a temporary chrony client using `server ntp.ww.cx iburst nts` or `chronyd -Q` with the equivalent server directive;
3. verify the external client actually selects/authenticates the NTS source and receives valid time;
4. set the Business159 observer's NTS expectation to `1`;
5. confirm the WW.CX and CreekCo public status APIs/pages report NTS available;
6. record final public NTS acceptance.

## Deferred

Still deferred:

- public IPv6/AAAA NTP or NTS acceptance;
- NTS for the alternate `time.ww.cx` hostname;
- multiple public time servers / DNS failover;
- legal-metrology or guaranteed-accuracy claims.
