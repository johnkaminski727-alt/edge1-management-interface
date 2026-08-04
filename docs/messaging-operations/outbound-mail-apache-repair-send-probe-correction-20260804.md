# Outbound-mail Apache repair send-probe correction

Date: 2026-08-04

## Observed audit result

The first live `ACTION=audit` invocation of the merged Phase B2 Apache proxy-mapping repair package stopped before evidence creation with:

```text
ERROR: direct send endpoint is not HTTP 403
```

The repository remained clean and `.git/index` remained owned by `wwadmin:wwadmin` mode `0644`. No Apache file was replaced, Apache was not reloaded, and no gateway, credential, provider, sender, DNS, firewall, listener, delivery, preparation, or message state changed.

## Root cause

The audit submitted an empty JSON object to `POST /outbound-mail/send`.

The live runtime validates request structure and sender selection before reaching the delivery-disable boundary. An empty object is therefore an invalid request and correctly returns HTTP `400`. The accepted disabled-runtime migration verifier already uses a syntactically valid canary with:

- an `example.invalid` recipient;
- a fixed non-production subject and body;
- `message_class=business_correspondence`;
- `confirm_send=true`.

That valid request reaches the live-sender authorization boundary and returns HTTP `403` with JSON error `delivery_disabled`. It does not prepare or send a message.

## Correction

`deploy/messaging/run-outbound-mail-apache-proxy-mapping-repair.sh` is a bounded wrapper around the already-reviewed repair script. It:

1. refuses a missing or symlinked original script;
2. creates a private temporary copy;
3. requires exactly one known empty-object send probe;
4. replaces only that probe with the accepted valid disabled-send canary;
5. adds an assertion that the JSON error is exactly `delivery_disabled`;
6. runs the temporary script with `GIT_OPTIONAL_LOCKS=0`;
7. removes the temporary copy on exit.

The wrapper refuses to run when the underlying script has drifted or already contains the corrected probe.

## Required sequence

After merging this correction, fast-forward clean Edge1 `main` to the exact merge commit and run the wrapper in audit mode:

```sh
sudo EXPECTED_COMMIT="<exact-merge-commit>" \
  ACTION=audit \
  sh deploy/messaging/run-outbound-mail-apache-proxy-mapping-repair.sh
```

The expected result is:

```text
readiness_state=ready_for_explicit_apache_proxy_mapping_repair_authorization
failures=0
```

Audit mode does not replace the Apache fragment or reload Apache.

## Preserved boundaries

This correction does not authorize:

- Apache fragment installation or reload;
- credential access or installation;
- provider or sender activation;
- DNS, firewall, certificate, or listener changes;
- external delivery;
- message preparation or sending;
- Business159 credential installation.
