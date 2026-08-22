# Edge1 Mail Gateway — Local Deployment Preflight

Date: 2026-08-22
Status: read-only operator preparation

## Purpose

Collect everything required to make a later local-only Postfix apply decision without modifying Postfix during discovery.

The preflight is intentionally separate from installation. It does not edit `/etc/postfix`, run `postmap`, reload/restart Postfix, change listeners, or touch DNS.

## Command

From an authenticated Edge1 operator session with the repository reconciled to current `main`:

```sh
cd /opt/edge1-management-interface
sh deploy/messaging/prepare-edge1-mail-gateway-local-preflight.sh
```

The script prints an evidence directory under `/tmp` by default. Set `OUTPUT_ROOT` to an approved durable evidence root if desired.

## Evidence collected

The package contains:

- repository HEAD and status when available;
- `postconf -n`;
- `postconf -M`;
- current TCP listeners;
- copies of current `main.cf` and `master.cf` for comparison only;
- relevant current Postfix values;
- currently active TCP/25 listener lines;
- detected existing `virtual_mailbox_domains`, `virtual_mailbox_maps`, and `virtual_transport` values;
- freshly rendered Edge1 Mail Gateway maps/fragments;
- SHA-256 manifest.

## Fail-closed checks

The preflight stops if:

- required tooling/config is unavailable;
- rendered configuration is not loopback-only;
- rendered relay-domain safety is missing;
- `ww.cx` appears in the v1 managed-domain map;
- live TCP/25 is exposed on a non-loopback address.

Existing Postfix virtual-domain settings are recorded as collisions for review rather than overwritten.

## Current expected live posture

Bounded Edge1 diagnostics on 2026-08-22 showed:

- Postfix active;
- TCP/25 listening on `127.0.0.1:25` only.

The preflight must independently verify that state in the authenticated operator session before any local apply work.

## Review gate after preflight

Do not install anything merely because the preflight passes.

Review:

1. repository state;
2. listener state;
3. relevant Postfix parameters;
4. collisions;
5. generated main/master fragments and domain maps.

A later local-only apply should be backup-first and should preserve loopback-only binding. Public SMTP exposure, DNS/MX changes, certificates, firewall changes, and outbound delivery remain separate explicit authorization boundaries.
