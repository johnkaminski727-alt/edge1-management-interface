# Outbound mail runtime configuration and state boundary

Date: 2026-08-04

## Objective

Separate future production activation files from the Git checkout while preserving the current repository-relative disabled deployment.

New components:

- path resolver: `server/outbound_mail_runtime_paths.py`;
- runtime application loader: `server/outbound_mail_runtime_application.py`;
- final suppression-aware runtime entrypoint: `server/outbound_mail_gateway_runtime_server.py`;
- validation: `tests/validate_outbound_mail_runtime_paths.py`.

No running service is changed by this source package.

## Approved roots

Absolute immutable runtime configuration is restricted to:

```text
/etc/wwcx
```

Absolute mutable state is restricted to:

```text
/var/lib/wwcx-outbound-mail
```

Repository-relative paths remain supported and retain the existing repository-root escape protection. This preserves the current disabled service while allowing a later runtime-only migration.

## Configuration files

The runtime loader can place the following outside Git:

```text
/etc/wwcx/outbound-mail-gateway.json
/etc/wwcx/outbound-mail-policy.json
/etc/wwcx/mail-identities.json
```

Absolute configuration files must:

- exist as regular files;
- remain inside `/etc/wwcx` after canonical resolution;
- have no final-file or parent-directory symlink;
- be root-owned in the production entrypoint;
- not be group- or world-writable.

The production runtime server does not expose a flag to disable root-ownership checks. Tests can instantiate the loader directly with a temporary non-root ownership exception, but that option is not available from the server command line.

## Mutable state

The runtime gateway configuration may point audit and preparation nonce state to:

```text
/var/lib/wwcx-outbound-mail/audit.jsonl
/var/lib/wwcx-outbound-mail/preparation-nonces.sqlite3
```

The suppression-aware entrypoint uses:

```text
/var/lib/wwcx-outbound-mail/delivery-state.sqlite3
```

Absolute state paths must:

- remain inside the state root after canonical resolution;
- have no final-file or parent-directory symlink;
- be regular files when they exist;
- have no group or world permissions when they exist.

A state file may be absent at configuration-load time when the service is expected to create it. The suppression database is different at send time: the suppression gate requires it to exist and fails closed before provider submission when it is absent.

## Final runtime entrypoint

`outbound_mail_gateway_runtime_server.py` combines:

- strict runtime path loading;
- existing admin, health, status, audit, preview, and authenticated preparation routes;
- the suppression-aware send route;
- loopback-only binding.

It starts with the existing committed files by default. A future deployment can provide absolute runtime paths:

```sh
/usr/bin/python3 /opt/edge1-management-interface/server/outbound_mail_gateway_runtime_server.py \
  --config /etc/wwcx/outbound-mail-gateway.json \
  --identities /etc/wwcx/mail-identities.json \
  --config-root /etc/wwcx \
  --state-root /var/lib/wwcx-outbound-mail \
  --suppression-database /var/lib/wwcx-outbound-mail/delivery-state.sqlite3 \
  --host 127.0.0.1 \
  --port 8104
```

This command is a design target only. The current systemd service has not been switched to it.

## Validation

The validator proves:

- repository-relative configuration remains compatible;
- absolute config under the approved root loads;
- absolute audit, nonce, and suppression paths resolve under the state root;
- repository and absolute path escapes fail closed;
- final-file and parent-directory symlinks fail closed;
- broad config and state permissions fail closed;
- overlapping config and state roots fail closed;
- runtime policy and identity files remain disabled when copied from the committed sources;
- loopback health works through the runtime application;
- the send route remains HTTP 403 because delivery is disabled.

## Migration work still required

1. Generate disabled runtime copies of gateway, policy, and identities under `/etc/wwcx`.
2. Move or initialize audit, nonce, and suppression state under `/var/lib/wwcx-outbound-mail` with the dedicated service account.
3. Add a reversible systemd drop-in pointing to the runtime entrypoint.
4. Validate the existing preparation API and Business159 route against the runtime copies.
5. Prove no Git working-tree file changes during runtime activation or rollback.
6. Build a separately gated activation-overlay generator for one provider and sender.
7. Keep every activation overlay unavailable until provider, canonical sender, DMARC, return-path, bounce/complaint handling, credentials, and exact pilot authorization are complete.

## Preserved boundaries

This package creates no `/etc` or `/var/lib` files on Edge1, changes no systemd unit, restarts no service, accesses no credential, selects no provider, enables no sender, changes no DNS, prepares no production message, and sends no mail.
