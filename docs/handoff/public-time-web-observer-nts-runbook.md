# WW.CX Public Time Web, Business159 Observer and NTS Runbook

## Objective

Publish a human-readable GMT/UTC clock and public WW.CX time-service instructions on both `ww.cx` and `creekco.ca`, back the page with an independent observer on `business159.web-hosting.com`, and prepare a guarded upgrade of the existing Edge1 NTP service to Network Time Security (NTS).

This work preserves the existing architecture:

- Edge1 remains the actual NTP/NTS service host;
- Business159 remains an independent outside observer and public website host;
- the private Edge1 Time Authority dashboard remains separate from the public web pages;
- `ntp.ww.cx` is the canonical public time hostname;
- `time.ww.cx` remains an alternate standard-NTP hostname.

## Public website

Website source is maintained in `johnkaminski727-alt/ww-cx-website`.

Public pages:

```text
https://ww.cx/time/
https://creekco.ca/time/
```

Each page:

- displays GMT / UTC;
- publishes `ntp.ww.cx` and `time.ww.cx` for standard NTP on UDP/123;
- publishes NTS instructions only with a dynamic status indicator;
- displays bounded external-observer metadata from Business159;
- clearly distinguishes the human-readable web clock from a precision synchronization protocol.

The browser fetches a same-origin endpoint at:

```text
/api/time-status.php
```

The PHP endpoint reads only:

```text
$HOME/shared/wwcx-time-service/public-status.json
```

The mutable status file stays outside both website document roots. The endpoint republishes only bounded fields needed for service health and the clock display.

When a fresh Business159 NTP observation exists, the endpoint estimates WW.CX time as the Business159 host clock plus the measured NTP offset. The browser anchors to that epoch and advances it using a monotonic browser timer. If the observer is missing or stale, the page labels the fallback and uses the visitor device UTC clock.

## Business159 observer

Repository assets:

```text
modules/time-authority/config/public-service-sources.json
tools/time_authority/ntp_rtt_probe.py
tools/time_authority/nts_ke_probe.py
tools/time_authority/build_public_time_status.py
tools/time_authority/observe-public-time-service-shared-host.sh
deploy/install-public-time-observer-shared-host.sh
deploy/public-time-observer-shared-host-smoke-test.sh
```

Install from a current checkout of `edge1-management-interface` on Business159:

```bash
sh deploy/install-public-time-observer-shared-host.sh
```

The installer:

1. requires Python 3.6 or newer;
2. installs an unprivileged observer under `$HOME/wwcx-public-time-observer`;
3. keeps measurement history under `$HOME/private/wwcx-time-authority`;
4. publishes only sanitized current status under `$HOME/shared/wwcx-time-service/public-status.json`;
5. runs an immediate NTP observation;
6. probes the NTS-KE endpoint without treating it as required before NTS activation;
7. installs an idempotent five-minute user-cron observation;
8. validates the generated public status document.

The NTP probe is a real UDP/123 NTPv4 client measurement from Business159. The NTS probe validates the TCP/4460 TLS certificate and requires ALPN `ntske/1`; it is an NTS-KE availability observation, not by itself proof of a completed authenticated NTS time exchange.

Before NTS activation the observer stores:

```text
$HOME/wwcx-public-time-observer/nts-expected = 0
```

After NTS has been published and externally accepted, rerun the observer installer with:

```bash
WWCX_NTS_EXPECTED=1 sh deploy/install-public-time-observer-shared-host.sh
```

Once expected, a failed certificate/ALPN NTS observation causes the observer run and public NTS status to fail closed.

## NTS architecture

The NTS server is the existing Edge1 `chronyd` instance. The reviewed fragment is:

```text
modules/time-authority/config/edge1-chrony-nts.conf
```

It configures:

```text
ntsport 4460
ntsservercert /etc/chrony/nts/ntp.ww.cx-fullchain.pem
ntsserverkey /etc/chrony/nts/ntp.ww.cx-privkey.pem
ntsdumpdir /var/lib/chrony
```

The base chrony configuration includes `/etc/chrony/conf.d` so the NTS feature stays separate from the standard NTP source/rate-limit policy.

Only the canonical hostname `ntp.ww.cx` is advertised for NTS in this phase. `time.ww.cx` remains a standard-NTP alternate unless a future certificate and acceptance explicitly add it as an authenticated NTS name.

## NTS certificate discovery

Before any certificate issuance or installation, inspect existing Edge1 certificate inventory without reading private-key contents:

```bash
sudo sh tools/time_authority/discover-nts-certificate-edge1.sh
```

The explicit `sh` invocation is intentional so this read-only helper does not depend on the source checkout preserving an executable mode bit.

If an existing certificate already covers `ntp.ww.cx`, review its lifecycle and matching key path. If no suitable certificate exists, certificate issuance is a separate privileged production action and must be explicitly approved before execution.

## NTS read-only preflight

Provide only reviewed source paths:

```bash
sudo env \
  WWCX_NTS_CERT_SOURCE=/reviewed/path/fullchain.pem \
  WWCX_NTS_KEY_SOURCE=/reviewed/path/privkey.pem \
  sh deploy/time-authority-nts-edge1-preflight.sh
```

The preflight verifies:

- `chrony.service` is active and standard NTP remains healthy;
- the installed `chronyd` reports NTS support;
- the certificate matches `ntp.ww.cx` and has at least seven days remaining;
- certificate and private key public keys match;
- the key can be read without an interactive passphrase;
- `ntp.ww.cx` still resolves to the reviewed Edge1 public IPv4;
- TCP/4460 is free or already owned by chronyd;
- the current chrony configuration parses;
- no mutation occurs.

## NTS local activation — privileged gate

This step installs certificate/key material and activates a new TCP/4460 listener. It must not be run without explicit production approval for both actions.

Required gates:

```text
WWCX_NTS_APPROVE_CERTIFICATE_INSTALL=YES
WWCX_NTS_APPROVE_NTS_LISTENER=YES
```

Command after approval:

```bash
sudo env \
  WWCX_NTS_APPROVE_CERTIFICATE_INSTALL=YES \
  WWCX_NTS_APPROVE_NTS_LISTENER=YES \
  WWCX_NTS_CERT_SOURCE=/reviewed/path/fullchain.pem \
  WWCX_NTS_KEY_SOURCE=/reviewed/path/privkey.pem \
  sh deploy/install-time-authority-nts-edge1.sh
```

The first-activation installer intentionally refuses to overwrite an existing staged NTS private key. Renewal/rotation must use a separately reviewed lifecycle procedure rather than silently replacing credential material.

Acceptance requires:

- chronyd returns to synchronized state;
- standard NTP UDP/123 still passes its packet smoke test;
- chronyd owns TCP/4460;
- a local TLS connection with SNI `ntp.ww.cx` verifies the public chain and negotiates ALPN `ntske/1`.

The installer does not publish TCP/4460 through the firewall.

## Public NTS firewall — privileged gate

Public IPv4 NTS-KE requires a separate explicit firewall approval:

```text
WWCX_NTS_APPROVE_PUBLIC_TCP4460=YES
```

After approval:

```bash
sudo env \
  WWCX_NTS_APPROVE_PUBLIC_TCP4460=YES \
  sh deploy/publish-time-authority-nts-firewall-edge1.sh
```

The helper follows the accepted UDP/123 firewall pattern:

- back up `/etc/nftables.conf` and the live ruleset;
- add only the reviewed IPv4 destination rule for TCP/4460;
- syntax-check the persistent file without loading it;
- insert the equivalent live rule before the public-web rule;
- preserve runtime Big Bird blocklist/logging controls by not reloading the full nftables ruleset;
- retain public IPv6 NTS as deferred.

## External NTS acceptance

After TCP/4460 publication:

1. run the Business159 observer and verify certificate + ALPN success;
2. perform a full authenticated NTS client test from a host outside Edge1, for example a temporary chrony client configured with `server ntp.ww.cx iburst nts`;
3. verify the client selects/authenticates the NTS source and receives valid time;
4. rerun the Business159 installer with `WWCX_NTS_EXPECTED=1`;
5. confirm both public pages change their NTS state to available;
6. record live acceptance evidence.

Do not call NTS fully accepted from a TLS-port check alone.

## Certificate renewal

Chronyd loads NTS server certificates at process start. Before live NTS activation is declared operational, identify the certificate manager that owns the approved source certificate and establish a reviewed renewal hook or runbook that restages the renewed certificate/key and restarts chronyd with standard NTP and NTS smoke tests.

Do not weaken private-key permissions or copy private-key contents into repository, website, logs or public observer output.

## Deferred

Not included in the initial package:

- public IPv6/AAAA NTP or NTS;
- NTS for the alternate `time.ww.cx` hostname;
- multiple Edge1 time servers or DNS failover;
- legal-metrology or guaranteed-accuracy claims.
