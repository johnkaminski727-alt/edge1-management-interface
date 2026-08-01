# Outbound mail Phase B2 parameter discovery — 2026-08-01

## Purpose

The committed WW.CX website bridge permits exactly `https://edge1.ww.cx/outbound-mail/api/v1`. The Phase B2 hostname is therefore `edge1.ww.cx`; it is not inferred or newly selected by this tool.

The remaining proposal inputs are:

- the existing approved certificate full-chain path on Edge1;
- the corresponding existing private-key path, identified by metadata only;
- the actual outbound NAT address measured from business159 and expressed as one `/32` or `/128`.

An A record for the website is not sufficient proof of the shared host's outbound source address.

## First live discovery result

The first authenticated Edge1 run completed at `2026-08-01T20:08:56Z` against commit `880edfeb3b79941a1d8f50a5eb92b1efe985dc61` and wrote evidence to:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-parameter-discovery/20260801T200856Z
```

It preserved every non-mutation boundary and confirmed unsigned preparation HTTP `401`, send HTTP `403`, the loopback listener, active Apache on port 443, and an enabled `edge1.ww.cx` vhost. Its only failure was a false health-path probe to `/healthz`, which correctly returned HTTP `404`; the gateway's real health route is `/outbound-mail/healthz` and returns HTTP `200`.

The enabled Apache vhost identifies the authoritative existing TLS references:

```text
/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
```

The full chain publicly identifies `edge1.ww.cx`, `pbx.ww.cx`, and `sip.ww.cx`, and was valid from July 19, 2026 through October 17, 2026 at the time of discovery. The private-key path was root-owned with mode `0600`; its contents were not read.

The original inventory reported two matching public certificate files because both `cert.pem` and `fullchain.pem` contain the same leaf certificate. It also reported five private-key paths because it inventoried every configured Apache vhost. Those are broad inventory counts, not ambiguity in the active `edge1.ww.cx` vhost.

## Business159 measurement

The separately reviewed website tool ran at `2026-08-01T20:09:23Z` against website commit `6d65ba2833d7ac20fa962f5457dedc45f75a2c47` and wrote evidence to:

```text
/home/wwcxjywl/shared/ww-cx-website/evidence/outbound-mail-client-discovery/20260801T200923Z
```

All three independent HTTPS services agreed on `162.0.217.71`, producing the exact proposed source restriction:

```text
162.0.217.71/32
```

The evidence manifest passed SHA-256 verification. No website configuration, secret, deployment, bridge, provider, sender, or message state changed.

## Corrected Edge1 discovery command

```sh
cd /opt/edge1-management-interface
sudo PROPOSED_CLIENT_CIDR=162.0.217.71/32 \
  sh tools/messaging/outbound_mail_phase_b2_parameter_discovery.sh
```

The corrected script requires clean `main`, exact host `edge1.ww.cx`, active loopback B1 service, HTTP `200` from `/outbound-mail/healthz`, HTTP `401` for unsigned preparation, and HTTP `403` for send.

It retains the broad certificate and key-path inventory, but proposal selection is based only on the enabled vhost that names `edge1.ww.cx`. It does not read private-key contents. Private-key handling is limited to pathname, ownership, mode, size, type, and `contents_read=no` metadata.

Evidence is written to:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-parameter-discovery/<UTC timestamp>/
```

The generated `candidate-parameters.env` contains the four proposal inputs, using an explicit unresolved marker for any value that has not passed validation.

When the enabled vhost resolves to one valid full-chain path and one existing mode-`0400` or mode-`0600` private-key path, and one exact client `/32` or `/128` is supplied, the expected state is:

```text
ready_for_phase_b2_proposal_validation
```

## Next safe step

After the corrected discovery evidence is accepted, run the existing Phase B2 proposal-validation audit with these four exact values:

```text
PROPOSED_HOSTNAME=edge1.ww.cx
PROPOSED_CLIENT_CIDR=162.0.217.71/32
CERTIFICATE_FULLCHAIN_PATH=/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
CERTIFICATE_PRIVATE_KEY_PATH=/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
```

That audit renders a candidate proxy configuration into restricted evidence only.

No live B2 change is performed by discovery or proposal validation. Proxy installation/reload, certificate/key-pair use, DNS, firewall, public exposure, website bridge activation, provider/sender activation, delivery, and messages remain separately validated execution steps with rollback and evidence.
