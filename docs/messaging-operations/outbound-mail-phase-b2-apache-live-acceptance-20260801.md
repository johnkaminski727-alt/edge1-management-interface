# Outbound mail Phase B2 Apache live acceptance

Date: 2026-08-01

## Outcome

The rollback-capable Phase B2 Apache activation completed successfully on `edge1.ww.cx`. The accepted evidence is:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-activation/20260801T221005Z
```

The activation used repository HEAD `9bfc9d0c494da11a4fb47fe38e7390f0b12d1444`, approved activation commit `d35fda6a3adcac2782ed6e8ed44ea8650a4d9df2`, and the accepted proposal evidence at `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/20260801T210934Z`.

## Exact installed scope

The activation installed one root-owned Apache fragment:

```text
/etc/apache2/wwcx-outbound-mail-preparation-api.conf
```

The existing TLS virtual host received exactly one additional line:

```apache
IncludeOptional /etc/apache2/wwcx-outbound-mail-preparation-api.conf
```

The fragment contains only these source-restricted routes:

```text
GET  /outbound-mail/api/v1/status
POST /outbound-mail/api/v1/prepare
```

Both routes are restricted to `162.0.217.71/32` and proxy only to the existing loopback gateway on `127.0.0.1:8104`. No send route and no wildcard route were installed.

## Validation

The following checks passed:

- `apache2ctl configtest` returned `Syntax OK`;
- Apache remained active and enabled;
- `wwcx-outbound-mail-gateway.service` remained active and enabled;
- the fragment was root-owned and mode `0644`;
- the approved include count was `1`;
- only one Apache configuration file referenced the preparation API routes;
- the gateway listener count on `127.0.0.1:8104` was `1`;
- the external listener count on port 8104 was `0`;
- the evidence `SHA256SUMS` manifest passed;
- `activation_summary_validation=PASS`;
- `B2_APACHE_ACTIVATION=PASS`;
- failures were `0`.

Unapproved local-source HTTPS canaries returned:

```text
status  = 403
prepare = 403
send    = 404
health  = 404
```

Direct loopback gateway checks returned:

```text
health          = 200
unsigned status = 401
send            = 403
```

The gateway status remained:

```text
state=disabled
preparation_api_enabled=true
runtime_secret_configured=true
external_delivery_enabled=false
policy_enabled=false
live_sender_count=0
providers_ready=0
```

## Preserved boundaries

The activation did not expose a certificate private key or read the HMAC secret. It did not generate a certificate, modify DNS or firewall policy, add a listener, enable the website bridge, enable a provider or sender, enable external delivery, or send a message.

The existing Apache certificate and key references were validated by Apache. The activation did not replace or export them.

## Rollback state

No rollback was required because all post-installation checks passed. The activation evidence preserves the prior vhost and fragment state and the exact applied diff. The committed rollback mode remains available and is drift-safe: it refuses to overwrite later Apache changes that do not match the accepted post-activation hashes.

## Next gate

The current state is:

```text
readiness_state=awaiting_business159_source_acceptance
```

The next operation is a credential-free canary from business159. The measured source must receive HTTP `401` from the unsigned status and prepare routes, proving that the source allow-list admitted the request and the gateway HMAC layer rejected the missing signature. The send and health routes must remain HTTP `404`, TLS verification must succeed, and redirects must remain disabled.

Only after that can a secure, non-disclosing credential-installation procedure be reviewed. Website bridge activation remains preparation-only; production delivery and any actual message remain out of scope until separately defined and validated.
