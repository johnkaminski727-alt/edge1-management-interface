# Outbound mail suppression-aware server deployment package

Date: 2026-08-04

## Purpose

Provide a reversible, evidence-producing deployment path for the suppression-aware loopback gateway entrypoint without enabling a provider, sender, external delivery, or message traffic.

Package:

- installer/auditor: `deploy/messaging/install-outbound-mail-suppression-server.sh`;
- empty-state initializer: `tools/messaging/initialize_outbound_mail_delivery_state.py`;
- validator: `tests/validate_outbound_mail_suppression_deployment.py`.

The package is committed but has not been executed on Edge1.

## Default action

The script defaults to:

```text
ACTION=audit
```

Audit verifies the host, exact repository commit, clean `main`, service account, current service state, listener boundary, safe-disabled runtime configuration, source validations, and current entrypoint. It writes restricted evidence but does not change systemd, restart the service, create the suppression database, or change mail flow.

An exact commit is always required:

```sh
EXPECTED_COMMIT=$(git rev-parse HEAD)
sudo EXPECTED_COMMIT="$EXPECTED_COMMIT" \
  sh deploy/messaging/install-outbound-mail-suppression-server.sh
```

## Installation authorization boundary

Installation is a production service-entrypoint change and is not authorized by the repository merge alone. It requires the exact explicit runtime gate:

```text
ACTION=install
SUPPRESSION_DEPLOYMENT_AUTHORIZED=yes
EXPECTED_COMMIT=<exact approved main commit>
```

No credential value is accepted by the script.

## Installation scope

The installer:

1. requires `edge1.ww.cx`, root execution, clean `main`, and exact approved commit;
2. discovers and requires the existing dedicated non-root gateway service account;
3. confirms the current service is active and port 8104 has no external listener;
4. verifies the runtime gateway, delivery, policy, provider, and sender gates remain disabled;
5. runs the source suppression-gate and real loopback-server tests;
6. creates `/var/lib/wwcx-outbound-mail` mode `0750` under the gateway service account;
7. initializes an empty mode-`0600` SQLite delivery-state database;
8. refuses installation if a delivery-state database already exists;
9. installs one root-owned systemd drop-in replacing only `ExecStart` with the suppression-aware entrypoint;
10. reloads systemd and restarts the existing gateway service;
11. validates service state, exact entrypoint, ownership, permissions, loopback listener, health, unsigned preparation rejection, safe status, and disabled send response;
12. captures source hashes, unit state, listeners, sanitized HTTP responses, journal output, and `SHA256SUMS`.

The installer never edits the committed or runtime gateway JSON, identity registry, provider profiles, sender allowlist, policy, DNS, firewall, certificate, or reverse-proxy configuration.

## Empty database initializer

The initializer creates only the schema defined by `server/outbound_mail_delivery_events.py`. It requires both tables to be empty and refuses an existing database containing delivery events or recipient state.

It never inserts:

- a synthetic event;
- a recipient hash;
- a suppression;
- a provider message identifier;
- message content;
- a credential.

## Automatic rollback

Once a database or drop-in mutation begins, an EXIT trap covers every nonzero shell exit, signal, failed command under `set -e`, and explicit failed post-check.

Rollback:

- restores the prior drop-in or removes the new one;
- reloads systemd;
- restarts the previous gateway entrypoint;
- preserves a newly created empty database under a timestamped `.rolled-back-*` name rather than deleting it;
- captures post-rollback service evidence and a manifest.

This closes the gap where an unexpected command failure could otherwise leave the new entrypoint partially installed.

## Verify action

After an authorized install:

```sh
sudo ACTION=verify \
  EXPECTED_COMMIT=<exact deployed commit> \
  sh deploy/messaging/install-outbound-mail-suppression-server.sh
```

Verify is read-only. It requires the suppression-aware entrypoint and database to be present and re-runs the bounded service, permission, listener, health, preparation, status, and disabled-send checks.

## Disable action

Disable is a production service change and requires the same explicit authorization flag. It refuses to alter a drifted drop-in. On an exact match, it removes the drop-in from active systemd configuration, restarts the original gateway entrypoint, and preserves the delivery-state database.

```sh
sudo ACTION=disable \
  SUPPRESSION_DEPLOYMENT_AUTHORIZED=yes \
  EXPECTED_COMMIT=<exact deployed commit> \
  sh deploy/messaging/install-outbound-mail-suppression-server.sh
```

## Preserved state

Even after a successful installation, the expected state remains:

```text
preparation_api_enabled=true
external_delivery_enabled=false
policy_enabled=false
providers_ready=0
live_sender_count=0
send_http=403
message_sent=no
```

The package does not authorize its own execution, install provider credentials, select a provider, provision a sender, change DMARC or other DNS, enable the send endpoint, or send a message.
