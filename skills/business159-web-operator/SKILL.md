---
name: business159-web-operator
description: Diagnose and operate WW.CX web applications on the Business159 shared host using bounded Business159 tools. Use for PHP, HTTP/HTTPS, document roots, redirects, .htaccess, staging/public separation, application health, deployment state, public/private exposure, domain/TLS diagnostics, and web-facing Big Bird or Operations Center components without duplicating the general authenticated operator.
---

# Business159 Web Operator

Compose with `business159-authenticated-operator`; specialize in the web/application layer.

Start with the narrowest evidence:

- `business159.web_status` for HTTP/HTTPS behavior.
- `business159.php_status` for PHP runtime state.
- `business159.domain_state` and `business159.tls_status` for domain/certificate diagnostics.
- `business159.deployment_status` and `business159.git_state` for release/source drift.
- `business159.edge1_bridge_status` when Operations Center data appears stale or missing.
- `business159.logs_summary` only when request/status evidence is insufficient.

For a 500/error investigation, combine PHP, HTTPS, deployment/Git, and bounded logs before considering raw shell. For routing/`.htaccess` issues, use staged filesystem control and show the diff before apply.

Keep private application data outside webroots and do not expose backup archives, `.env` files, signing material, credentials, or private operational records. Treat certificate replacement, DNS changes, authentication changes, and public exposure of a previously private path as separately gated production/security actions.

After a web mutation, verify syntax where applicable, exact file/release state, HTTPS response, and the relevant application endpoint. Do not declare success from process/file presence alone.
