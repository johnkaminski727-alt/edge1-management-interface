# Outbound mail Phase B2 — Apache proposal audit

Date: 2026-08-01

## Purpose

This package validates the exact Apache proposal discovered on `edge1.ww.cx` without installing a route, changing Apache, reading the HMAC secret, reading certificate private-key contents, changing DNS or firewall state, activating the website bridge, enabling delivery, or sending a message.

The prior generic Phase B2 audit rendered an nginx candidate. Live discovery established that Apache 2 is the active and enabled port-443 service, so an Apache-specific proposal is required before any live configuration work.

## Accepted discovery input

The corrected discovery ran through authenticated SSH at `2026-08-01T20:41:48Z` against repository HEAD `b5614ffc7ff309b50c8b799e155d41cf67433811`.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-parameter-discovery/20260801T204148Z
```

Accepted discovery facts:

```text
proposed_hostname=edge1.ww.cx
proposed_client_cidr=162.0.217.71/32
health_http=200
unsigned_api_status_http=401
send_probe_http=403
active_edge1_vhost_count=2
active_certificate_reference_count=1
active_private_key_reference_count=1
fullchain_reference_count=1
private_key_reference_count=1
active_tls_pair_in_enabled_vhost=yes
readiness_state=ready_for_phase_b2_proposal_validation
failures=0
pending_decisions=0
```

The two active `edge1.ww.cx` vhost blocks are expected: one non-TLS block and one TLS block are present in the enabled site. This is not certificate ambiguity. The enabled site contains one approved full-chain reference and one approved private-key reference.

## Exact proposal

```text
PROPOSED_HOSTNAME=edge1.ww.cx
PROPOSED_CLIENT_CIDR=162.0.217.71/32
CERTIFICATE_FULLCHAIN_PATH=/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
CERTIFICATE_PRIVATE_KEY_PATH=/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
ACTIVE_VHOST=/etc/apache2/sites-enabled/edge1.ww.cx.conf
```

## Let's Encrypt path handling

The active Apache site uses the standard Let's Encrypt `live` paths. Those paths are symlinks that rotate to versioned files under `/etc/letsencrypt/archive/edge1.ww.cx/` during renewal.

The audit validates the live-to-archive symlink chain by pathname and metadata only:

- the configured live path must be the exact approved path;
- the live path must be a symlink;
- the resolved target must remain under the expected archive directory;
- the target must be a root-owned regular file;
- the private-key target must be mode `0400` or `0600` and non-empty;
- the public full chain is checked for hostname coverage and more than seven days of remaining validity.

The audit does not read private-key contents. It does not parse, hash, display, compare, or export the key. Certificate/key-pair matching is deferred to the separately authorized installation validation, where Apache's own configuration test can verify the pair without exposing it.

## Candidate fragment

The reviewed template is:

```text
deploy/messaging/outbound-mail-preparation-api-apache.conf.example
```

The audit renders this evidence-only candidate:

```text
candidate-apache-fragment.conf
```

The fragment is designed to be included only inside the existing TLS `VirtualHost` for `edge1.ww.cx`. It contains exactly:

- `GET /outbound-mail/api/v1/status`;
- `POST /outbound-mail/api/v1/prepare`;
- source restriction to `162.0.217.71/32`;
- proxying only to `127.0.0.1:8104`;
- denial of other methods at those exact routes.

It contains no send route and no wildcard API route.

## Audit command

```sh
cd /opt/edge1-management-interface
sudo sh tools/messaging/outbound_mail_phase_b2_apache_proposal_audit.sh
```

The exact proposal values are safe defaults in the reviewed script. They may also be supplied explicitly, but any change requires a new reviewed proposal.

## Expected result

```text
readiness_state=ready_for_explicit_b2_apache_authorization
failures=0
```

Evidence is written under:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/<UTC timestamp>/
```

## Non-mutation contract

Every successful run records:

```text
certificate_private_key_contents_read=no
certificate_key_pair_match_deferred_to_install=yes
hmac_secret_read=no
proxy_config_installed=no
proxy_service_reloaded=no
certificate_generated=no
dns_modified=no
firewall_modified=no
public_listener_added=no
website_bridge_enabled=no
provider_or_sender_enabled=no
external_delivery_enabled=no
message_sent=no
```

No live Apache change is performed by this proposal audit.

## Next gate

After proposal evidence is accepted, the live installer must be separately reviewed before execution. It must:

1. verify exact host, clean `main`, accepted proposal evidence, and approved commit ancestry;
2. back up the active vhost and any new include path into restricted evidence;
3. install one root-owned Apache include fragment;
4. insert one include directive only inside the existing TLS vhost for `edge1.ww.cx`;
5. run `apache2ctl configtest` before reload;
6. use a graceful Apache reload only after syntax success;
7. verify source restriction from business159 and denial from an unapproved source;
8. verify HMAC authentication, replay rejection, continued send denial, and loopback gateway binding;
9. automatically restore the backup and reload the prior configuration if validation fails;
10. leave providers, senders, external delivery, retention, and production messages disabled.
