# Outbound mail Phase B2 Apache proposal live acceptance

Date: 2026-08-01

## Accepted execution

The Apache-specific Phase B2 proposal audit was executed through authenticated SSH by `wwadmin` on `edge1.ww.cx`; the audit itself ran as `root` through `sudo`.

Accepted evidence:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/20260801T210934Z
```

Accepted repository state:

```text
branch=main
head_commit=d89cbb06d5ecd171e67c1a281beb58ef16a1f24c
proposal_package_commit=105ea0f2dd79a3bbc5a09c5c7c7ed49eab5a0e0d
```

## Accepted proposal facts

```text
captured_at=2026-08-01T21:09:34Z
host=edge1.ww.cx
principal=root
proposed_hostname=edge1.ww.cx
proposed_client_cidr=162.0.217.71/32
active_vhost=/etc/apache2/sites-enabled/edge1.ww.cx.conf
active_vhost_resolved=/etc/apache2/sites-available/edge1.ww.cx.conf
health_http=200
status_http=200
unsigned_api_status_http=401
send_probe_http=403
edge1_servername_count=2
fullchain_reference_count=1
private_key_reference_count=1
certificate_fullchain_resolved=/etc/letsencrypt/archive/edge1.ww.cx/fullchain2.pem
certificate_private_key_resolved=/etc/letsencrypt/archive/edge1.ww.cx/privkey2.pem
certificate_private_key_contents_read=no
certificate_key_pair_match_deferred_to_install=yes
readiness_state=ready_for_explicit_b2_apache_authorization
failures=0
```

The two `ServerName edge1.ww.cx` occurrences represent the enabled non-TLS and TLS virtual-host blocks. The enabled TLS block contains exactly one approved full-chain reference and exactly one approved private-key reference.

The full-chain target was root-owned, mode `0644`, and non-empty. The private-key target was root-owned, mode `0600`, and non-empty. Private-key contents were not read, hashed, displayed, or exported by the proposal audit.

The evidence manifest passed SHA-256 verification for every captured file.

## Accepted candidate

The evidence-only Apache fragment contains exactly two routes:

- `GET /outbound-mail/api/v1/status`;
- `POST /outbound-mail/api/v1/prepare`.

Both routes are restricted to `162.0.217.71/32` and proxy only to `127.0.0.1:8104`. Other methods are denied. The candidate contains no send route and no wildcard API route.

## Verified non-mutation boundary

The accepted run recorded:

```text
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

No Apache file was installed, no service was reloaded, and no public route was activated by this audit.

## Next gate

The proposal evidence is accepted as the prerequisite for a separately reviewed, rollback-capable Apache activation package. Activation must preserve the existing port-443 listener, install only one exact include fragment inside the existing TLS virtual host, run Apache configuration validation before a graceful reload, deny unapproved sources, preserve direct HMAC authentication and send denial, and retain a verified rollback path.

After Edge1 activation, an unsigned request from the measured business159 source must return HTTP `401`. That external source acceptance is required before the website bridge can be activated.
