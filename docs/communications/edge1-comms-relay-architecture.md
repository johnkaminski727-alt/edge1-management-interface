# WW.CX Edge1 Communications Relay Architecture

Status: production-ready repository implementation  
Version: 1.0.0  
Protocols: IRC plus NNTP reader/poster

## Purpose

Edge1 Communications Relay gives WW.CX a standards-oriented synchronous and durable discussion layer. IRC is the live conversation plane. NNTP is the durable threaded discussion and archival plane. Both share local identity, authorization, storage, moderation, retention and audit controls.

```text
IRC clients -> IRC service ----+
                               +-> shared policy/storage -> SQLite WAL
NNTP clients -> NNTP service --+          |
                                          +-> commsctl
                                          +-> loopback read-only control API/UI
```

The unified production process is `server/edge1_commsd.py`. Standalone protocol entry points remain laboratory tools.

## Security boundary

The shipping configuration binds IRC, NNTP and the control UI only to loopback. A non-loopback IRC or NNTP bind is rejected unless `network_exposure.enabled=true` and TLS certificate/key paths are configured. The control API is always required to remain loopback-only.

Runtime controls include:

- total and per-source connection ceilings;
- command token-bucket rate limits;
- failed-authentication throttling shared across reconnects from a source address;
- connection idle timeouts;
- bounded line and article sizes;
- PBKDF2-HMAC-SHA256 password hashes with random salts and per-account iteration metadata;
- minimum password length enforcement;
- server-side authenticated-user identity on NNTP posts;
- denial of anonymous posts to moderated groups;
- explicit denial of NNTP federation commands;
- no IRC server-to-server implementation.

IRC SASL PLAIN and NNTP AUTHINFO are permitted on loopback. Any non-loopback protocol listener must use TLS.

## IRC

Version 1.0 implements CAP/SASL, NICK/USER registration, PING/PONG, JOIN/PART, PRIVMSG/NOTICE, TOPIC, NAMES, WHO, KICK and channel mode `+m`/`-m`. Founder, `moderator`, and `irc-operator` roles have operator authority. The server advertises only capabilities it implements (`sasl`).

IRC history is disabled by default. If enabled, channel joins and channel PRIVMSG events are retained for the configured interval; direct-message bodies are not persisted.

## NNTP

Version 1.0 implements CAPABILITIES, MODE READER, AUTHINFO USER/PASS, LIST variants, GROUP, ARTICLE/HEAD/BODY/STAT, OVER/XOVER, NEXT/LAST, POST and QUIT. `IHAVE`, `CHECK`, and `TAKETHIS` return a federation-disabled response.

Initial groups are `wwcx.general`, `wwcx.announce`, `wwcx.projects.bigbird`, `wwcx.projects.edge1`, `wwcx.telecom`, `wwcx.security`, and `wwcx.test`. Announcement and security groups are moderated.

Authenticated posts receive a canonical `username <username@users.ww.cx>` From identity plus `X-WWCX-Authenticated-User`. This prevents protocol clients from impersonating another authenticated WW.CX account in the durable article store.

## Storage and retention

SQLite runs with foreign keys, busy timeout, WAL journal mode and normal synchronous durability. Each account stores the password-derivation iteration count used for its credential so future default changes do not invalidate existing accounts.

Retention is enforced at process startup and at a configured maintenance interval. Per-newsgroup article retention, IRC-history retention and audit retention are independent. The CLI also provides `maintenance prune` for explicit operator maintenance.

## Control surface

The HTTP control service is read-only and loopback-only. Important endpoints are:

```text
GET /healthz
GET /api/comms/status
GET /api/comms/news/groups
GET /api/comms/audit?limit=100
```

Mutation methods return HTTP 405.

## Deployment model

The systemd unit uses a dedicated `wwcx-comms` identity, strict filesystem protection, no capabilities, restricted address families, namespace/realtime restrictions, process visibility restrictions, task/file-descriptor ceilings and memory ceilings.

The installer is dry-run-first. Apply requires root, a clean `main` checkout and optionally an exact expected commit. It preserves prior unit/config/service state, validates configuration and the systemd unit, records hashes and deployment evidence, and performs a local IRC/NNTP/control smoke test when activation is requested. Any activation failure triggers restoration of the prior state.

## Deliberate non-goals for 1.0

Public DNS/firewall/certificate provisioning, Internet exposure, IRC federation, NNTP peering, automatic IRC-to-NNTP mirroring, binaries and unrestricted anonymous posting are outside the 1.0 production boundary. They require separate design and authorization.
