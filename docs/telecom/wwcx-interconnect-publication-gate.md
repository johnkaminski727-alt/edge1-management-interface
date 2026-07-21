# WW.CX Interconnect Publication Gate

Status: repository-ready; public information publication and live SIP activation remain separate controlled changes.

## Purpose

This gate separates three states that must not be conflated:

1. **Repository ready** — source, templates, public copy, machine-readable metadata, validation, and rollback instructions exist.
2. **Information published** — the HTTPS information site is publicly reachable, but it explicitly states that public SIP traffic is not accepted.
3. **Interconnect active** — a public SIP listener, certificate, firewall allowance, peer authorization, backend route, and controlled acceptance tests are complete.

Publishing the information site does not authorize or imply carrier status, a commercial agreement, emergency-calling capability, numbering authority, STIR/SHAKEN authority, or acceptance of production traffic.

## Current repository assets

- `src/web/interconnect/index.html` — staging information page.
- `src/web/interconnect/service.json` — machine-readable staging profile with `public_activation: false`.
- `deploy/interconnect/publish-interconnect-site.sh` — copies static information assets only.
- `deploy/interconnect/apache/interconnect.ww.cx.conf.example` — reviewed template, not an enabled virtual host.
- `deploy/interconnect/validate-staging-assets.sh` — repository staging validation.
- `reports/interconnect-readiness.md` and `.json` — generated readiness state.
- `docs/telecom/wwcx-interconnect-rollback-runbook.md` — rollback instructions.

## Gate A — public information site

The information site may be published only after all of the following are recorded:

- [ ] Public wording reviewed and still marked staging/not publicly active.
- [ ] `service.json` validates and retains `public_activation: false`.
- [ ] No credentials, peer secrets, private keys, customer information, internal routes, or private contacts are present.
- [ ] Hosting location and document root are confirmed.
- [ ] DNS change is separately approved and recorded.
- [ ] HTTPS certificate issuance or installation is separately approved and recorded.
- [ ] Apache or shared-hosting configuration passes syntax validation before reload.
- [ ] HTTP redirects to HTTPS.
- [ ] `index.html` and `service.json` return HTTP 200 over HTTPS.
- [ ] Security headers and disabled directory listing are verified.
- [ ] Rollback consists of disabling the site configuration or removing the publication mapping without touching telephony services.

Gate A must not open TCP 5061, alter Asterisk or FreePBX, change firewall policy, or activate a carrier peer.

## Gate B — external signaling activation

Live SIP signaling remains blocked until all items below are complete:

- [ ] Carrier or peer identity and authorization method are verified.
- [ ] Commercial and legal prerequisites are approved outside the repository.
- [ ] Certificate chain and hostname validation pass for `interconnect.ww.cx`.
- [ ] Kamailio configuration validation passes with default-deny behavior.
- [ ] Public REGISTER, unknown peers, malformed requests, and open-relay attempts are rejected.
- [ ] Firewall changes are reviewed, bounded to required sources where possible, and reversible.
- [ ] Asterisk backend remains loopback-only and uses a restricted inbound context.
- [ ] Caller-ID, privacy, codec, DTMF, rate-limit, fraud, media, RTP/SRTP, logging, and alert policies are approved.
- [ ] Emergency-calling behavior is explicitly defined; no unsupported emergency capability is advertised.
- [ ] STIR/SHAKEN handling is explicitly defined; no signing authority is claimed without verified authorization.
- [ ] External TLS and SIP OPTIONS acceptance tests pass.
- [ ] Existing PBX trunks and calls pass regression checks.
- [ ] Rollback is rehearsed and evidence is retained.

## Advertisement channels

Once Gate A is complete, WW.CX may reference the informational profile through approved, accurate channels such as:

- the main WW.CX website;
- direct technical correspondence with prospective peers;
- approved carrier qualification packages;
- a future industry directory or peering profile where eligibility is verified.

DNS SRV/NAPTR records are protocol discovery mechanisms, not marketing claims. They must not point peers toward an inactive service unless the published profile clearly remains staging and no traffic is accepted.

## Stop conditions

Stop before any action that would:

- change DNS, certificates, firewall policy, public listeners, authentication, Asterisk/FreePBX, routing, or live traffic without a separately approved production change;
- advertise unverified regulatory, carrier, emergency-calling, numbering, or STIR/SHAKEN status;
- contact or enroll with an external directory, exchange, carrier, regulator, or vendor without approved outreach;
- expose secrets or private operational details.

## Evidence record

For each gate execution, retain:

- date, operator, repository commit, and change ticket or approval reference;
- pre-change DNS, HTTP, listener, and service state;
- configuration syntax results and checksums of published assets;
- post-change HTTP/TLS or SIP acceptance evidence, as applicable;
- explicit statement of what was not changed;
- rollback result or rollback readiness confirmation.

## Current decision

The repository satisfies the **repository-ready** state. It does not by itself prove that the information site is publicly reachable or that the SIP interconnect is active. Gate A and Gate B must be executed and evidenced independently.