# Asterisk PJSIP Runtime Cause Audit Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/asterisk-pjsip-runtime-cause/20260801T021810Z/audit.txt
SHA-256: 3554bc698e47090dacf41ff054597138fba3841968836e6eafa08fb5a0f29f84
```

The audit exited `0`, reported two warnings and zero failures, and made no configuration, service, listener, route, certificate, firewall, package, call, or logger change.

## Accepted observations

- Asterisk `22.10.1` remained active and enabled at boot.
- The running PID remained `1651722`.
- Zero active channels, calls, and processed calls were observed.
- `chan_pjsip` and the `res_pjsip` module family remained loaded.
- Asterisk retained UDP `127.0.0.1:5061` ownership.
- The PJSIP CLI registry still returned no transport objects.
- The deterministic duplicate transport category remained present:
  - custom `[0.0.0.0-udp]` at `127.0.0.1:5061`;
  - generated `[0.0.0.0-udp]` at `0.0.0.0:5060`.
- Kamailio retained port `5060` ownership.
- The inspected Asterisk unit journal and bounded current Asterisk log tail contained no retained diagnostic proving whether the generated bind failed, the duplicate category was rejected, or the runtime registry entered a partial state.
- The relevant configuration file hashes matched the preceding policy audit.

## Cause classification

The configuration is defective because the same transport category name is defined twice with different bind addresses. The runtime state is also incomplete because a live Asterisk-owned SIP socket exists without a corresponding CLI transport object.

The exact startup failure mechanism remains unproven. No repair should be selected solely from inference, and the generated FreePBX transport file must not be edited directly.

A repair will require a controlled maintenance event that preserves pre-change configuration and runtime evidence, changes only the authoritative FreePBX/custom source, validates generated output, restarts or reloads only through an approved procedure, and has a tested rollback. That maintenance event is not part of this acceptance.

## Expanded exposure priority

Asterisk's built-in HTTPS server on port `8089` is a legitimate platform surface for HTTPS and secure WebSocket consumers when those features are intentionally configured. The current host also shows other Asterisk interfaces that require explicit inventory and activation decisions:

- AMI on loopback TCP `5038`;
- HTTP on loopback TCP `8088`;
- HTTPS/WebSocket on wildcard TCP `8089`, effectively limited by the current firewall to loopback and WireGuard;
- PJSIP on loopback UDP `5061`;
- Asterisk-owned high UDP sockets observed at `55539` and `59177`, whose feature or media-range purpose has not yet been attributed;
- enabled HTTP URIs including Prometheus metrics, media-over-WebSocket, and `/ws`.

A comprehensive, host-wide listener exposure audit is therefore the next priority. It must enumerate every socket, process owner, interface scope, systemd socket, container-published port, Asterisk management/API/media surface, and effective firewall path before any further public activation.

## Decision boundary

Accepted:

- current health and boot persistence;
- the evidence and hash above;
- the unresolved duplicate PJSIP transport defect;
- the need for a comprehensive listener/interface exposure inventory;
- continued offline-only alerting laboratory operation.

Not authorized or performed:

- Asterisk restart or reload;
- PJSIP or FreePBX configuration edits;
- listener or firewall changes;
- public activation of ARI, AMI, WebSocket, media, SIP, RTP, CAP feeds, calls, pages, or attention tones.
