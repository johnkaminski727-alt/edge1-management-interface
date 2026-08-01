# Outbound mail Phase B2 — read-only readiness audit

Date: 2026-08-01

## Purpose

This package prepares the separately gated Phase B2 TLS reverse-proxy decision without installing or exposing anything.

Phase B1 is already accepted live on `edge1.ww.cx` as authenticated preparation on `127.0.0.1:8104`. External delivery, policy activation, delivery providers, and live sender identities remain disabled.

Phase B2 would eventually expose exactly two HMAC-authenticated preparation routes through an approved TLS reverse proxy:

- `GET /outbound-mail/api/v1/status`;
- `POST /outbound-mail/api/v1/prepare`.

The audit does not authorize or perform that exposure.

## Audit command

The read-only audit is:

```text
tools/messaging/outbound_mail_phase_b2_readiness_audit.sh
```

It must run as root because service state, restricted runtime-file metadata, firewall inventories, and certificate file metadata are not generally available to an unprivileged account. Root execution does not authorize the script to read the installed HMAC secret or certificate private-key contents.

## Baseline inventory mode

With no proposal variables, the audit verifies the accepted B1 runtime and records the exact decisions still required:

```sh
cd /opt/edge1-management-interface
sudo sh tools/messaging/outbound_mail_phase_b2_readiness_audit.sh
```

A successful baseline inventory reports:

```text
readiness_state=awaiting_explicit_b2_parameters
```

That is not B2 authorization or public readiness. It means the current safe state was inspected and the exact hostname, client source, and certificate paths have not yet been selected.

## Proposal-validation mode

After the user separately selects the exact proposal, the same audit may be run with all four values supplied:

```sh
cd /opt/edge1-management-interface

sudo \
  PROPOSED_HOSTNAME='approved-lowercase-fqdn.example' \
  PROPOSED_CLIENT_CIDR='192.0.2.10/32' \
  CERTIFICATE_FULLCHAIN_PATH='/approved/path/fullchain.pem' \
  CERTIFICATE_PRIVATE_KEY_PATH='/approved/path/privkey.pem' \
  sh tools/messaging/outbound_mail_phase_b2_readiness_audit.sh
```

The values above are format examples only. They are not approved WW.CX production values.

The client source must be one exact IPv4 `/32` or IPv6 `/128` address. A broader network requires an explicit design decision and a revised reviewed package rather than silently widening access.

## What the audit verifies

### Repository and accepted state

- exact host `edge1.ww.cx`;
- clean `main` with no untracked files;
- accepted B1 live-state commit is an ancestor;
- reviewed B2 template baseline is an ancestor;
- protected B2 files are unchanged after that baseline;
- staged nginx template exposes exactly the status and prepare routes;
- no send route or wildcard API proxy is present.

### Live B1 boundary

- `wwcx-outbound-mail-gateway.service` is active and enabled;
- service principal is `wwcx-mail-gateway`;
- port 8104 is bound only to `127.0.0.1`;
- health and public status return HTTP 200;
- unsigned authenticated status returns HTTP 401;
- send remains denied with HTTP 403;
- preparation authentication is enabled with a configured runtime secret;
- external delivery and policy remain disabled;
- no provider is ready and no live sender exists;
- runtime config and drop-in are root-owned mode `0644`;
- the environment credential file is root-owned mode `0600`.

The audit uses metadata only for the environment file and never reads it.

### Existing exposure and host controls

- listeners on ports 8104 and 443;
- installed and active nginx, Apache, httpd, or Caddy components;
- existing web-server references to the preparation API paths;
- nftables, iptables, ip6tables, and UFW state when those tools are available.

The firewall commands are inventory commands only. No rule is added, removed, enabled, or reloaded.

### Proposed B2 parameters

When all four proposal values are supplied, the audit verifies:

- lowercase, non-wildcard FQDN syntax;
- one exact client source address;
- current read-only DNS resolution;
- full-chain file existence, root ownership, public certificate metadata, hostname coverage, and more than seven days of remaining validity;
- private-key file existence, regular-file type, root ownership, mode `0400` or `0600`, and nonzero size;
- candidate rendering from the reviewed template into the restricted evidence directory only.

The audit does not parse, validate, hash, print, or otherwise read the private-key contents. Certificate/key-pair matching remains an authorized-install verification because a matching test requires opening the private key.

## Readiness states

- `not_ready` — one or more verified safety checks failed;
- `awaiting_explicit_b2_parameters` — baseline is safe, but no exact proposal was supplied;
- `awaiting_separately_authorized_dns_or_parameter_resolution` — proposal is otherwise valid but a separately gated dependency, such as DNS resolution, remains unresolved;
- `ready_for_explicit_b2_authorization` — the read-only proposal checks passed. This state still does not authorize installation, reload, certificate access, firewall/DNS changes, or external testing.

## Evidence

Evidence is written under:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness/<UTC timestamp>/
```

The directory is mode `0700`. It includes repository state, service properties, listener inventories, sanitized endpoint results, runtime-file metadata, proxy matches, firewall inventories, proposal validation, public certificate details, a candidate nginx file when all proposal values are supplied, pending decisions, failures, and `SHA256SUMS`.

It does not include:

- the HMAC secret;
- the contents or hash of the HMAC environment file;
- certificate private-key contents or a private-key hash;
- message bodies;
- provider credentials;
- any sent message.

## Non-mutation contract

Every run records:

```text
hmac_secret_read=no
certificate_private_key_read=no
proxy_config_installed=no
proxy_service_reloaded=no
certificate_generated=no
dns_modified=no
firewall_modified=no
public_listener_added=no
website_bridge_enabled=no
provider_or_sender_enabled=no
message_sent=no
```

The script must not install a proxy configuration, issue or renew a certificate, reload a web server, alter DNS or firewall state, enable a public listener, activate the website bridge, activate a provider or sender, or send mail.

## Separate B2 authorization still required

A later B2 action requires explicit authorization naming:

1. the exact API hostname;
2. the certificate full-chain and private-key paths or approved certificate-issuance method;
3. the exact source IPv4 `/32` or IPv6 `/128`;
4. the selected reverse proxy and destination configuration path;
5. whether an existing port-443 service will be modified or reloaded;
6. any DNS record change;
7. any firewall rule change;
8. an external signed canary source;
9. rollback and evidence locations.

B2 authorization must remain separate from website bridge activation, retention, provider credentials, live senders, external delivery, and production messages.

## Stop conditions

Stop before:

- reading, exporting, displaying, rotating, or replacing the B1 HMAC secret;
- reading or testing certificate private-key contents;
- installing the candidate nginx configuration;
- issuing, renewing, replacing, or deploying a certificate;
- reloading or restarting nginx, Apache, Caddy, or another proxy;
- changing DNS, firewall rules, public listeners, or public routes;
- activating the WW.CX website bridge;
- enabling retention apply or scheduling;
- installing provider credentials or enabling a sender;
- enabling delivery or sending any message.
