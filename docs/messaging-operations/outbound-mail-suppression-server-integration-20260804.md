# Outbound mail suppression-aware server integration

Date: 2026-08-04

## Objective

Integrate the hashed-recipient suppression gate into the loopback outbound-mail HTTP send route without changing the committed disabled gateway, provider, sender, policy, or delivery state.

Implementation:

- `server/outbound_mail_gateway_suppressed_server.py`;
- `tests/validate_outbound_mail_suppression_server.py`.

## Route behavior

The entrypoint subclasses the existing gateway handler and changes only:

```text
POST /outbound-mail/send
```

Every other route remains delegated to the existing handler, including:

- admin console and static assets;
- health and status;
- authenticated preparation status;
- authenticated `prepared_not_sent` preparation;
- local preview and audit reads.

The service still refuses a non-loopback bind.

## Send sequence

The guarded send route performs:

1. existing gateway, policy, identity, and audit-path loading;
2. existing bounded JSON-body parsing;
3. existing explicit `confirm_send` extraction;
4. existing recipient normalization;
5. required suppression-database availability check;
6. hashed-recipient suppression lookup;
7. identity-aware send callable only after suppression preflight passes;
8. minimized preflight metadata in the result.

A missing suppression database or active suppression raises the existing delivery-disabled error class. The HTTP route returns `403 delivery_disabled` before any provider callable runs.

## Suppression database path

The default entrypoint path is:

```text
var/outbound-mail/delivery-state.sqlite3
```

A runtime deployment may provide an absolute path with:

```text
--suppression-database /var/lib/wwcx-outbound-mail/delivery-state.sqlite3
```

The database must exist before any live send attempt. Missing state fails closed rather than treating every recipient as allowed.

## Local validation

`tests/validate_outbound_mail_suppression_server.py` starts isolated loopback servers with synthetic provider callables and proves:

- existing `/outbound-mail/healthz` remains available;
- missing state returns HTTP 403 and the provider callable is not invoked;
- an active complaint suppression returns HTTP 403 without exposing the recipient;
- an allowed recipient returns HTTP 202 and invokes the provider callable exactly once;
- the response contains only recipient count and suppression count, not addresses;
- non-send POST routes remain delegated to the existing handler.

No SMTP connection is used in validation.

## Deployment still required

This integration is source-complete but not deployed. A separately authorized deployment package must:

1. create the production suppression database and parent directory under the gateway service account;
2. initialize the database without synthetic events;
3. change the systemd service entrypoint from `outbound_mail_gateway_server.py` to `outbound_mail_gateway_suppressed_server.py`;
4. pass the absolute suppression-database path;
5. retain loopback binding and the existing authenticated reverse-proxy boundary;
6. validate the preparation API remains healthy and delivery remains disabled;
7. validate missing-state and active-suppression requests cannot open an SMTP socket;
8. capture service, listener, file ownership, mode, journal, and rollback evidence;
9. provide automatic rollback to the previous entrypoint if any health or safety check fails.

Changing the running service entrypoint is a production deployment action and is not authorized by this source change alone.

## Preserved boundaries

This integration does not create the live suppression database, change systemd, restart a service, enable a provider or sender, install credentials, change DNS, prepare a production message, or send mail. The committed gateway, policy, sender allowlist, and send endpoint remain disabled.
