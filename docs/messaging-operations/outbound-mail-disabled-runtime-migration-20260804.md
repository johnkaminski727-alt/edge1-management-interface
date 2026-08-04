# Disabled outbound-mail runtime migration

Date: 2026-08-04

## Objective

Move the already active preparation-only gateway from repository-relative configuration and mutable state to strict runtime roots without enabling delivery:

```text
/etc/wwcx
/var/lib/wwcx-outbound-mail
```

The migration preserves the existing HMAC preparation service, source configuration, reverse-proxy boundary, and safe-disabled mail state. It does not read the HMAC secret or any provider credential.

Package:

- bundle builder: `tools/messaging/build_outbound_mail_disabled_runtime_bundle.py`;
- migration wrapper: `deploy/messaging/install-outbound-mail-disabled-runtime-migration.sh`;
- validation:
  - `tests/validate_outbound_mail_disabled_runtime_bundle.py`;
  - `tests/validate_outbound_mail_disabled_runtime_migration.py`.

The package is committed source only and has not been executed on Edge1.

## Default audit

The wrapper defaults to:

```text
ACTION=audit
```

Audit requires:

- root execution on `edge1.ww.cx`;
- clean repository `main` at an explicit `EXPECTED_COMMIT`;
- the existing active non-root gateway service;
- the existing preparation-enabled runtime config;
- loopback-only port 8104;
- passing runtime-bundle and runtime-path validation.

Audit generates a proposed bundle and evidence but changes no service, runtime file, or state database.

## Bundle guarantees

The bundle copies the current gateway, policy, and identity documents. It permits exactly three gateway changes:

```text
paths.policy
paths.audit_jsonl
preparation_api.nonce_store
```

The resulting paths are:

```text
/etc/wwcx/outbound-mail-policy-runtime.json
/var/lib/wwcx-outbound-mail/audit.jsonl
/var/lib/wwcx-outbound-mail/preparation-nonces.sqlite3
```

The identities document is copied unchanged to:

```text
/etc/wwcx/mail-identities-runtime.json
```

The builder refuses any source state with:

- gateway, deployment, external-delivery, or send-endpoint activation;
- a selected or enabled provider;
- enabled policy or SMTP cutover;
- global identity activation;
- a non-empty live sender allowlist;
- any live-enabled identity;
- a disabled preparation API for a production bundle.

It reads no environment secret and modifies no source file.

## Authorized installation

Installation is a production service-entrypoint change and requires:

```text
ACTION=install
RUNTIME_MIGRATION_AUTHORIZED=yes
EXPECTED_COMMIT=<exact approved main commit>
```

The installer creates new files rather than overwriting the current preparation config:

```text
/etc/wwcx/outbound-mail-gateway-runtime.json
/etc/wwcx/outbound-mail-policy-runtime.json
/etc/wwcx/mail-identities-runtime.json
```

The original remains unchanged:

```text
/etc/wwcx/outbound-mail-gateway.json
```

The wrapper records and rechecks its SHA-256 before completion.

## State migration

With the service stopped, the wrapper:

- copies the existing audit JSONL as the dedicated service account, mode `0600`;
- copies the existing SQLite nonce database through SQLite's read-only backup API;
- creates an empty delivery-state database only when one does not already exist;
- validates an existing delivery-state database's owner, group, mode, and exact schema;
- never inserts a recipient, event, suppression, provider ID, or synthetic record.

The state root must be owned by the gateway service user and group. Its mode must have no group-write or world permissions. The config root must be root-owned and not group- or world-writable.

## Systemd boundary

One higher-priority drop-in is installed:

```text
/etc/systemd/system/wwcx-outbound-mail-gateway.service.d/40-runtime-paths.conf
```

It changes only `ExecStart`, selecting:

```text
server/outbound_mail_gateway_runtime_server.py
```

with the strict runtime config/state roots and suppression database. Lower-priority preparation environment and security settings remain in force.

## Post-install validation

A successful installation must prove:

- service active under the same dedicated non-root account;
- exact runtime entrypoint;
- root-owned mode-`0644` runtime configuration files;
- service-owned mode-`0600` audit, nonce when present, and suppression files;
- exact delivery-state schema;
- HTTP 200 health and status;
- unsigned authenticated-preparation status returns HTTP 401;
- preparation API remains enabled and its runtime secret remains configured;
- external delivery and policy remain disabled;
- no provider is ready and no sender is live;
- send returns HTTP 403;
- no external listener on port 8104;
- original preparation config SHA-256 unchanged.

The wrapper does not perform a signed preparation request because it does not read the HMAC secret.

## Automatic rollback

The EXIT rollback trap is installed before either install or disable can mutate systemd.

Before mutation, the wrapper preserves the exact prior drop-in state. On any failed command, signal, or post-install check it:

1. restores the prior drop-in, or removes/moves a newly created one;
2. reloads systemd;
3. restarts the previous gateway entrypoint;
4. moves only files created by the failed migration to timestamped `.rolled-back-*` names;
5. preserves any pre-existing suppression database;
6. removes only newly created empty directories when possible;
7. rechecks and records whether the original preparation config remained unchanged;
8. captures rollback service evidence and SHA-256 inventory.

## Disable

Disable also requires explicit authorization. It first compares the active drop-in to the exact expected content. If it has drifted, disable refuses to continue.

On an exact match, it removes the runtime drop-in from active systemd configuration and restarts the previous entrypoint. Runtime configuration and state files are preserved for evidence and possible reviewed reuse.

If restart or validation fails, the same EXIT rollback restores the runtime drop-in and restarts the runtime entrypoint.

## Preserved boundaries

This migration package does not:

- read or rotate the HMAC secret;
- read or install SMTP/provider credentials;
- change DNS, firewall, certificate, or reverse-proxy configuration;
- enable a provider, sender, policy, send endpoint, or external delivery;
- prepare a production message;
- send mail.

Migration execution remains a separately authorized production change.
