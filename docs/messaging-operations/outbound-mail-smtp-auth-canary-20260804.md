# Outbound mail SMTP authentication-only canary

Date: 2026-08-04

## Objective

Prove a selected SMTP submission endpoint, TLS certificate path, STARTTLS capability, AUTH capability, and credential pair without attempting message delivery.

Components:

- authorization schema: `schemas/messaging/smtp-auth-canary-authorization.schema.json`;
- canary: `tools/messaging/outbound_mail_smtp_auth_canary.py`;
- validator: `tests/validate_outbound_mail_smtp_auth_canary.py`.

The package is source-only and has not been executed with provider credentials.

## Command boundary

After all authorization and credential prerequisites pass, the SMTP sequence is exactly:

```text
connect
EHLO
STARTTLS with the default verified system trust store
EHLO after TLS
AUTH through the standard SMTP login mechanism
NOOP
RSET
QUIT
```

The implementation contains no message-submission methods. It does not issue an envelope sender, recipient, content, or submission command.

`RSET` clears any transaction state even though no transaction is opened.

## Runtime settings

The canary reads the same environment-variable names committed in the `smtp_submission` gateway profile:

```text
WWCX_MAIL_SMTP_HOST
WWCX_MAIL_SMTP_PORT
WWCX_MAIL_SMTP_USERNAME
WWCX_MAIL_SMTP_PASSWORD
```

Values are read only after authorization-file validation reaches the runtime-settings step. No credential value is accepted as a command-line option, printed, written to output, or included in an error.

The raw host and username are reduced to SHA-256 in the result. The password has no output representation.

## Authorization file

A canary run requires a private regular JSON file outside Git with mode `0600` or stricter. It contains:

```text
contract=wwcx.smtp-auth-canary-authorization.v1
authentication_canary_authorized=true
provider_profile=smtp_submission
expected_host_sha256=<exact runtime host hash>
expected_port=<exact runtime port>
expected_username_sha256=<exact runtime username hash>
expires_at=<future timestamp no more than 24 hours away>
mail_from_authorized=false
recipient_authorized=false
message_authorized=false
```

The canary refuses:

- an expired or longer-than-24-hour authorization;
- a host, port, or username mismatch;
- missing or extra fields;
- any authorization of message activity;
- broad authorization-file permissions;
- authorization or output inside a Git working tree;
- missing STARTTLS;
- missing post-TLS AUTH;
- rejected authentication;
- malformed provider profile or environment values.

The authorization file contains no password.

## Sanitized evidence

A successful result contains:

- provider profile;
- host SHA-256;
- port;
- username SHA-256;
- authorization expiry;
- STARTTLS and AUTH capability;
- TLS protocol and cipher name;
- peer-certificate SHA-256;
- authenticated state;
- NOOP, RSET, and QUIT response codes;
- explicit false markers for envelope, recipient, content, submission, sent-message, and credential-output state.

The canary does not enable the provider in gateway configuration. Successful authentication is necessary evidence, not delivery authorization.

## Execution prerequisites

A live run requires separate explicit authorization for credential use and authenticated provider access. Before execution:

1. identify the exact provider endpoint and port;
2. install credentials outside Git under the gateway service account;
3. calculate host and username hashes without disclosing values;
4. create a short-lived private authorization file;
5. verify the gateway provider and delivery gates remain disabled;
6. capture network destination, service account, environment variable names, and evidence directory;
7. run the canary once;
8. preserve sanitized output and revoke/rotate credentials if validation fails or exposure is suspected.

A live canary must not be combined with provider activation, sender activation, DNS changes, or a pilot message.

## Remaining work after a successful canary

- verify the credential is authorized for the exact canonical sender;
- verify the provider return-path and bounce behavior;
- complete complaint and unsubscribe handling;
- publish and validate monitoring-only DMARC after mailbox readiness and explicit DNS authorization;
- generate and review the runtime provider/sender activation overlay;
- authorize one exact owned-recipient pilot message;
- enable the provider/sender only for the controlled pilot window;
- automatically roll back after the pilot or on any failure.

## Preserved boundaries

This package does not install or inspect a real credential, contact a provider during CI, enable a provider or sender, change DNS/firewall/certificates, create a message transaction, prepare a production message, or send mail.
