# Outbound-mail Apache proxy-target repair

Date: 2026-08-04

## Live evidence

The first Phase B2 mapping repair changed the two preparation mappings from `ProxyPass` to `ProxyPassMatch` and passed local fail-closed checks. The subsequent Business159 credential-free canary still returned HTTP `404` for both preparation routes while public send and health remained HTTP `404`.

Accepted observations:

- Business159 egress: `162.0.217.71`;
- Edge1 Apache access log saw the Business159 requests;
- source authorization passed for Business159, because the result was not HTTP `403`;
- direct loopback preparation status remained HTTP `401`;
- local unapproved TLS requests remained HTTP `403`;
- no credential was read or installed;
- no provider, sender, policy, delivery, preparation, or message state was enabled.

## Root cause

Apache HTTP Server documents that when `ProxyPassMatch` is used inside `<LocationMatch>` without a backreference, the original request URL is appended to the configured backend URL.

The installed fragment supplied a complete backend path:

```apache
ProxyPassMatch "http://127.0.0.1:8104/outbound-mail/api/v1/status"
```

For a request to `/outbound-mail/api/v1/status`, Apache therefore constructed an effective backend path equivalent to the configured path plus the original request path. The gateway correctly returned HTTP `404` for that doubled path.

The corrected mapping supplies only the fixed loopback origin:

```apache
ProxyPassMatch "http://127.0.0.1:8104"
```

Apache then appends the exact path matched by the anchored `<LocationMatch>` expression, producing the intended backend URL.

## Bounded repair

`deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-target.sh` supports:

- `ACTION=audit`, the default, which performs no mutation;
- `ACTION=install`, gated by `APACHE_PROXY_TARGET_REPAIR_AUTHORIZED=yes`;
- `ACTION=rollback`, requiring a validated accepted-repair evidence directory.

The repair:

1. requires clean exact `main` at an explicit commit;
2. verifies Apache and the gateway are active;
3. verifies port `8104` remains IPv4 loopback-only;
4. verifies the current fragment contains exactly the two known faulty targets;
5. verifies direct unsigned status is HTTP `401`;
6. verifies a valid `example.invalid` disabled-send canary returns HTTP `403` and `error=delivery_disabled`;
7. verifies local unapproved preparation requests remain HTTP `403`;
8. verifies public TLS send and health remain HTTP `404`;
9. changes exactly two proxy target lines;
10. runs `apache2ctl configtest` before a graceful reload;
11. provides automatic rollback by restoring the exact prior fragment if post-change verification fails;
12. stores root-owned SHA-256 evidence outside the repository.

## Required sequence

After merge, fast-forward Edge1 `main` to the exact merge commit and run the audit:

```sh
sudo EXPECTED_COMMIT="<exact-merge-commit>" \
  ACTION=audit \
  sh deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-target.sh
```

Expected audit state:

```text
readiness_state=ready_for_explicit_apache_proxy_target_repair_authorization
failures=0
```

After explicit authorization, install with:

```sh
sudo EXPECTED_COMMIT="<exact-merge-commit>" \
  ACTION=install \
  APACHE_PROXY_TARGET_REPAIR_AUTHORIZED=yes \
  sh deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-target.sh
```

Expected installed state:

```text
readiness_state=awaiting_business159_source_acceptance
failures=0
```

The Business159 credential-free source-acceptance audit must then be rerun. The required external result remains HTTP `401` for both preparation routes and HTTP `404` for public send and health.

## Preserved boundaries

This repair does not authorize or perform:

- credential access or installation;
- provider or sender activation;
- policy or external-delivery activation;
- DNS, firewall, certificate, or listener changes;
- public exposure of send or health routes;
- message preparation or sending;
- Business159 website bridge activation.
