# Outbound mail suppression send gate

Date: 2026-08-04

## Objective

Refuse outbound submission before any provider callable runs when required suppression state is unavailable or any normalized recipient hash has an active permanent-bounce, complaint, or unsubscribe suppression.

Implementation:

- `server/outbound_mail_suppression_gate.py`;
- `tests/validate_outbound_mail_suppression_gate.py`.

## Recipient handling

The gate receives the gateway's already-normalized recipient list and converts each address to a lowercase SHA-256 digest. Suppression lookups and error results use hashes only. The gate does not return or store raw recipient addresses.

## Fail-closed state requirement

Production submission requires the suppression SQLite database to exist. If it is absent, the gate raises `SuppressionStateUnavailableError` before invoking the send callable.

An optional `required=false` mode exists only for health and readiness inspection. It must not be used for production submission.

## Active suppression behavior

If one or more recipient hashes are actively suppressed, the gate raises `SuppressedRecipientError` before the send callable runs. The error contains only:

- suppressed recipient count;
- recipient hashes in structured state;
- bounded suppression reasons.

It does not expose addresses, provider payloads, message bodies, or credentials.

## Allowed submission behavior

When the database exists and no recipient is suppressed, the gate invokes the supplied identity-aware send callable exactly once and adds a minimized result:

```json
{
  "suppression_preflight": {
    "checked": true,
    "recipient_count": 1,
    "suppressed_recipient_count": 0
  }
}
```

The gate does not modify the request, confirmation, audit path, gateway configuration, policy, identities, or provider response.

## Integration boundary

The current module is a tested reusable guard but is not yet wired into the live HTTP server or systemd deployment. Production integration still requires:

1. add a runtime path for the suppression database;
2. update the server send route to call `guarded_identity_send` instead of the unguarded send callable;
3. deploy the state database under the gateway service account;
4. prove the database is mode `0600` and writable only by the service account;
5. validate missing-state and active-suppression HTTP responses;
6. prove no SMTP socket opens when suppression preflight fails;
7. include suppression status in the controlled-pilot preflight evidence;
8. retain automatic suppression removal as prohibited.

## Preserved boundaries

This gate does not expose a listener, inspect provider credentials, connect to SMTP, change suppression state, remove a suppression, activate a provider or sender, prepare a message, or send mail by itself. The committed gateway and delivery gates remain disabled.
