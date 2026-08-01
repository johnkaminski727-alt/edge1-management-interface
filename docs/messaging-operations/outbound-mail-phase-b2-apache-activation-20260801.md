# Outbound mail Phase B2 Apache activation package

Date: 2026-08-01

## Purpose

This package activates only the two reviewed preparation API routes inside the existing `edge1.ww.cx` TLS virtual host. It does not create a listener, change DNS or firewall rules, generate or replace a certificate, read or export the HMAC credential, activate a provider or sender, enable external delivery, or send a message.

The package consumes accepted proposal evidence:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/20260801T210934Z
```

## Exact live change

The activation installs one root-owned mode `0644` fragment:

```text
/etc/apache2/wwcx-outbound-mail-preparation-api.conf
```

It inserts one line inside the unique TLS `VirtualHost` that contains all three approved facts:

```text
ServerName edge1.ww.cx
SSLCertificateFile /etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
SSLCertificateKeyFile /etc/letsencrypt/live/edge1.ww.cx/privkey.pem
```

The inserted line is:

```text
IncludeOptional /etc/apache2/wwcx-outbound-mail-preparation-api.conf
```

No other virtual-host content may change.

## Activation preflight

The wrapper refuses activation unless all of these are true:

1. it runs as `root` on `edge1.ww.cx`;
2. the repository is clean `main` at the operator-supplied `EXPECTED_COMMIT`;
3. the proposal package and operator-supplied approved activation commit are ancestors of `HEAD`;
4. protected outbound-mail files match the approved activation commit;
5. the accepted proposal evidence is root-owned, mode `0700`, manifest-valid, failure-free, and contains every exact accepted fact;
6. the gateway and Apache services are active and enabled;
7. the gateway remains bound only to `127.0.0.1:8104`;
8. direct gateway health is `200`, unsigned preparation status is `401`, and send is `403`;
9. the enabled vhost resolves exactly to `/etc/apache2/sites-available/edge1.ww.cx.conf`;
10. no Apache configuration already contains the preparation routes or approved include line;
11. Apache configuration is valid before mutation.

## Mutation and automatic rollback

Before changing Apache, the wrapper stores restricted backups of the active vhost and the proposed fragment state. It renders the fragment from the reviewed repository template and verifies that all placeholders are replaced, the exact source restriction occurs twice, and no send route exists.

It then:

1. installs the fragment;
2. inserts exactly one approved include line in the unique TLS virtual host;
3. proves that the include line is the only vhost change;
4. runs `apache2ctl configtest`;
5. reloads only `apache2.service`;
6. verifies Apache remains active;
7. confirms an unapproved local source receives `403` on both preparation routes;
8. confirms HTTPS send and health routes remain absent with `404`;
9. confirms the direct gateway still returns `401` for unsigned preparation status and `403` for send.

If any post-mutation check fails or the process is interrupted, the wrapper restores the exact vhost backup, restores or removes the fragment according to its prior state, reruns Apache configuration validation, reloads Apache, and records automatic rollback evidence.

## Successful intermediate state

A successful Edge1 activation records:

```text
proxy_config_installed=yes
proxy_service_reloaded=yes
approved_source_external_canary=not_yet_run
readiness_state=awaiting_business159_source_acceptance
external_delivery_enabled=no
message_sent=no
```

The activation is not fully accepted until an unsigned HTTPS status request from business159, whose measured source is `162.0.217.71/32`, returns HTTP `401`. A different source must remain denied.

## Manual rollback

The same wrapper supports `ACTION=rollback` with the exact successful activation evidence directory in `ROLLBACK_EVIDENCE`. It refuses rollback if the live vhost or fragment has changed since activation, preventing unrelated later Apache work from being overwritten.

A successful rollback restores the pre-activation vhost and fragment state, validates Apache, reloads it, confirms no preparation route remains in Apache configuration, and preserves direct gateway authentication and send-denial behavior.

## Remaining gates

- Edge1 Apache activation: prepared, not yet executed.
- Business159 source acceptance: not yet executed.
- Website bridge credential provisioning: not yet executed.
- Website bridge activation: not yet executed.
- Provider, sender, retention, and external delivery activation: not configured.
- Production message: not defined or sent.
