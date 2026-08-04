# Outbound-mail Phase B2 Apache proxy-mapping repair

Date: 2026-08-04

## Incident summary

The credential-free Business159 source-acceptance canary reached the accepted Edge1 public address `89.147.109.253` from the expected Business159 egress address `162.0.217.71`, with valid TLS and no redirects. Both public preparation routes returned HTTP `404` instead of the required unsigned HMAC response HTTP `401`. Public send and health remained absent with HTTP `404`.

Read-only Edge1 diagnostics proved:

- Apache and `wwcx-outbound-mail-gateway.service` were active;
- the enabled `edge1.ww.cx` TLS vhost and preparation fragment were present;
- the vhost included the fragment exactly once;
- an unapproved local TLS source received HTTP `403` on both preparation routes;
- the direct loopback gateway returned HTTP `401` for unsigned preparation status;
- the Business159 request appeared in the Edge1 Apache access log with source `162.0.217.71` and HTTP `404`;
- the local and public endpoints presented the same Edge1 certificate.

This isolates the defect to the proxy mapping inside the matched Apache authorization container. The existing fragment uses plain `ProxyPass` inside `<LocationMatch>`. Apache documents `ProxyPassMatch` as the reverse-proxy mapping form used inside `<LocationMatch>`. The source restriction matches correctly, but an approved request passes authorization and then falls through to local URL handling, producing HTTP `404` rather than reaching the gateway HMAC boundary.

## Exact source correction

The repaired fragment preserves the two anchored `<LocationMatch>` containers, methods, source restrictions, backend URLs, timeouts, reverse mappings, and no-send boundary. It changes exactly two directive names:

```diff
-    ProxyPass "http://127.0.0.1:8104/outbound-mail/api/v1/status" retry=0 connectiontimeout=5 timeout=30
+    ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/status" retry=0 connectiontimeout=5 timeout=30

-    ProxyPass "http://127.0.0.1:8104/outbound-mail/api/v1/prepare" retry=0 connectiontimeout=5 timeout=30
+    ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/prepare" retry=0 connectiontimeout=5 timeout=30
```

No vhost, certificate, DNS, firewall, listener, gateway runtime, credential, provider, sender, policy, delivery, or message configuration is changed by the source package.

## Bounded repair wrapper

The repair wrapper is:

```text
deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-mapping.sh
```

It defaults to `ACTION=audit`. The audit requires root on `edge1.ww.cx`, a clean exact `main` commit, active Apache and gateway services, loopback-only port `8104`, the exact enabled vhost/include relationship, the expected legacy two-line proxy mapping, direct gateway HTTP `401`/`403`, local unapproved-source HTTP `403`, and absent public send/health routes.

The root-level Git status check runs with `GIT_OPTIONAL_LOCKS=0` so audit and install cannot refresh the operator-owned Git index.

### Read-only audit

```sh
cd /opt/edge1-management-interface

EXPECTED_COMMIT=$(git rev-parse HEAD)

sudo EXPECTED_COMMIT="$EXPECTED_COMMIT" \
  ACTION=audit \
  sh deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-mapping.sh
```

A passing audit records:

```text
proxy_mapping_defect_confirmed=yes
proposed_directive_change_count=2
apache_reloaded=no
readiness_state=ready_for_explicit_apache_proxy_mapping_repair_authorization
failures=0
```

## Separately authorized install

Live installation changes the existing root-owned fragment and gracefully reloads Apache. It requires the explicit gate:

```text
APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED=yes
```

Invocation after audit acceptance and exact-commit authorization:

```sh
sudo EXPECTED_COMMIT="$EXPECTED_COMMIT" \
  ACTION=install \
  APACHE_PROXY_MAPPING_REPAIR_AUTHORIZED=yes \
  sh deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-mapping.sh
```

The wrapper:

1. backs up the exact live fragment;
2. proves the candidate differs only by the two directive names;
3. installs the candidate mode `0644`, root-owned;
4. runs `apache2ctl configtest`;
5. gracefully reloads only `apache2.service`;
6. verifies Apache remains active;
7. confirms local unapproved sources remain HTTP `403`;
8. confirms direct unsigned status remains HTTP `401`;
9. confirms public send and health remain HTTP `404`;
10. writes a restricted SHA-256 evidence directory.

Any failed post-mutation condition or interruption triggers automatic rollback to the exact prior fragment, another config test, and another graceful Apache reload.

A successful local repair records:

```text
proxy_mapping_repaired=yes
proposed_directive_change_count=2
apache_reloaded=yes
approved_source_external_canary=pending
readiness_state=awaiting_business159_source_acceptance
failures=0
```

## Required external acceptance

After a successful repair, rerun the credential-free Business159 audit. Acceptance still requires:

```text
measured_egress_address=162.0.217.71
unsigned_status_http=401
unsigned_prepare_http=401
https_send_http=404
https_health_http=404
approved_source_admitted=yes
hmac_boundary_confirmed=yes
readiness_state=ready_for_secure_bridge_credential_installation
failures=0
```

Do not install the Business159 credential until this external acceptance passes.

## Preserved boundaries

The audit and repair package do not read, copy, rotate, install, print, hash, or transmit an HMAC or provider credential. They do not enable the website bridge, provider, sender, policy, send endpoint, external delivery, or any message traffic. No message is prepared or sent. DNS, firewall, certificates, public listeners, and the gateway runtime remain unchanged.
