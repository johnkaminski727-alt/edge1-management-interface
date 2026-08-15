# WW.CX NTS Certificate Lifecycle Plan — 2026-08-15

## Verified live readiness

Read-only Edge1 inspection established:

- `chronyd` 4.3 reports `+NTS` support;
- standard WW.CX NTP remains synchronized and healthy;
- TCP/4460 is currently unused;
- `ntp.ww.cx` and `time.ww.cx` resolve to reviewed Edge1 IPv4 `89.147.109.253`;
- Apache owns TCP/80 and serves requests carrying `Host: ntp.ww.cx`;
- Certbot has the Apache authenticator installed;
- existing Certbot lineages cover `edge1.ww.cx`, `pbx.ww.cx`, `sip.ww.cx`, `interconnect.ww.cx`, `portal.ww.cx`, and `vpn.ww.cx`;
- no existing certificate covers `ntp.ww.cx`;
- no Certbot pre/deploy/post renewal-hook files were present at inspection time.

The dedicated NTS identity will therefore be `ntp.ww.cx`. The alternate `time.ww.cx` remains standard NTP only in this phase.

## Dedicated certificate issuance

Repository helper:

```text
deploy/issue-time-authority-nts-certificate-edge1.sh
```

Protected gate:

```text
WWCX_NTS_APPROVE_CERTIFICATE_ISSUANCE=YES
```

The helper requests a new ECDSA certificate with the dedicated Certbot lineage name `ntp.ww.cx` using `certbot certonly --apache --non-interactive`. It deliberately does not pass `--agree-tos`; if the already configured ACME account cannot issue non-interactively under its existing terms, issuance fails closed rather than implicitly accepting new terms.

Before issuance it rechecks standard NTP health, DNS, Apache/TCP80 ownership, and absence of an existing matching certificate or `ntp.ww.cx` lineage. After issuance it verifies hostname coverage, minimum remaining validity, certificate/private-key match, and records only public certificate and private-key metadata. It does not install credentials into chronyd or change TCP/4460 firewall state.

Expected Certbot paths after successful issuance:

```text
/etc/letsencrypt/live/ntp.ww.cx/fullchain.pem
/etc/letsencrypt/live/ntp.ww.cx/privkey.pem
```

## Local NTS activation

Existing reviewed installer:

```text
deploy/install-time-authority-nts-edge1.sh
```

Protected gates:

```text
WWCX_NTS_APPROVE_CERTIFICATE_INSTALL=YES
WWCX_NTS_APPROVE_NTS_LISTENER=YES
```

Source paths are the dedicated Certbot lineage above. The installer stages copies under `/etc/chrony/nts`, installs the reviewed chrony fragment, restarts chronyd, requires resynchronization, revalidates standard NTP, and performs a local certificate/ALPN NTS-KE smoke test. It does not publish TCP/4460 through the perimeter firewall.

## Public NTS-KE publication

Existing reviewed firewall helper:

```text
deploy/publish-time-authority-nts-firewall-edge1.sh
```

Protected gate:

```text
WWCX_NTS_APPROVE_PUBLIC_TCP4460=YES
```

It adds only the reviewed IPv4 TCP/4460 rule to the live `inet wwcxfw input` chain and persistent `/etc/nftables.conf`, preserving runtime Big Bird controls by not reloading the complete ruleset.

## Certbot renewal integration

Repository sources:

```text
deploy/time-authority-nts-certbot-deploy-hook.sh
deploy/install-time-authority-nts-renewal-hook-edge1.sh
```

Protected installation gate:

```text
WWCX_NTS_APPROVE_RENEWAL_HOOK_INSTALL=YES
```

Installed path:

```text
/etc/letsencrypt/renewal-hooks/deploy/50-wwcx-ntp-chrony-nts
```

The hook is lineage-scoped: all Certbot renewals other than `/etc/letsencrypt/live/ntp.ww.cx` are immediate no-ops. For the NTS lineage it validates hostname, remaining lifetime, and certificate/key match; backs up the currently staged chronyd credentials; atomically stages the renewed pair with restricted permissions; restarts chronyd; requires resynchronization; verifies UDP/123 and TCP/4460 ownership; and verifies local NTS-KE TLS trust plus ALPN `ntske/1`. On post-staging failure it restores the prior staged credentials and restarts chronyd.

The hook installer intentionally does not execute the hook against the live NTS lineage. A controlled Certbot renewal/deploy-hook validation remains a separate acceptance step after initial NTS activation.

## External acceptance

NTS is not accepted merely because TCP/4460 answers TLS. Required final evidence remains:

1. Business159 verifies the public NTS-KE certificate and ALPN `ntske/1`;
2. an independent external chrony client performs an authenticated NTS time exchange with `server ntp.ww.cx iburst nts`;
3. Business159 is switched to `WWCX_NTS_EXPECTED=1`;
4. both public time pages show NTS available from the external-observer state;
5. live acceptance evidence is recorded.

## Approval boundaries

No certificate issuance, certificate/key installation, chronyd NTS listener activation, TCP/4460 firewall publication, or Certbot renewal-hook installation is authorized by this document itself. Each corresponding production gate must be backed by explicit user authorization before execution.
