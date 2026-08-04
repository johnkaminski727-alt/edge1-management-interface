# Outbound mail Phase E provider readiness

Date: 2026-08-04

## Objective

Turn the committed disabled outbound-mail configuration into an exact, machine-readable provider-activation blocker report without reading credentials, querying providers or DNS, changing runtime state, or sending a message.

## Tool

```sh
python3 tools/messaging/outbound_mail_phase_e_readiness.py --pretty
```

To assert that the repository remains in the expected safely disabled state:

```sh
python3 tools/messaging/outbound_mail_phase_e_readiness.py \
  --pretty \
  --require-safe-disabled \
  --output /tmp/outbound-mail-phase-e-readiness.json
```

The auditor reads only:

- `config/messaging/outbound-mail-gateway.json`;
- `config/messaging/outbound-mail-policy.json`;
- `config/messaging/mail-identities.json`.

It reports environment-variable **names** required by provider profiles, but never reads or returns environment-variable values.

## Current expected result

The committed repository is intentionally classified as:

```text
readiness_state=safe_disabled
ready_for_provider_activation=false
runtime_credentials_inspected=false
network_or_dns_queries_performed=false
message_prepared=false
message_sent=false
```

The report preserves the current facts that:

- provider selection is `none`;
- the SMTP profile is disabled;
- gateway, policy, external-delivery, send-endpoint and SMTP-cutover gates are disabled;
- global identity activation is disabled;
- the live sender allowlist is empty;
- every sender profile is live-disabled.

## Blocker classes

The tool identifies exact blockers across:

1. gateway and policy activation gates;
2. provider selection and credential boundaries;
3. sender allowlisting and profile activation;
4. mailing-address and footer policy;
5. provider-side inventory and sender capability;
6. SPF, DKIM, DMARC and return-path alignment;
7. bounce, complaint and suppression handling;
8. controlled pilot recipient and message authorization.

A partially enabled configuration is classified `unsafe_partial_activation` rather than being treated as progress.

## Intended activation sequence

1. Complete the provider-object inventory and strict reconciliation.
2. Select one provider and review terms, limits and acceptable-use conditions.
3. Select one named sender with proven provider-side sender capability.
4. Capture SPF, DKIM, DMARC and return-path evidence for that domain.
5. Define bounce, complaint and suppression handling.
6. Prepare a runtime-only activation overlay and rollback package.
7. Install credentials through an approved secret path.
8. Authorize one WW.CX-controlled pilot recipient and one exact pilot message.
9. Enable one provider and one sender only, run the pilot, and validate provider acceptance, receipt and audit linkage.
10. Roll back immediately if any gate, delivery result or evidence check fails.

## Preserved boundaries

This readiness package does not authorize or perform:

- provider login or credential capture;
- acceptance of provider commercial terms;
- DNS, SPF, DKIM or DMARC changes;
- provider, sender, policy, gateway or send-endpoint activation;
- bounce or complaint endpoint exposure;
- production message traffic;
- public correspondence-record activation.
