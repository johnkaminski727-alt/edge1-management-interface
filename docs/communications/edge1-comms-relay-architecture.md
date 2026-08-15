# WW.CX Edge1 Communications Relay Architecture

Status: implemented foundation, network exposure not activated  
Version: 0.1.0  
Protocols: IRC/IRCv3 subset and NNTP reader/poster subset

## Purpose

Edge1 Communications Relay provides a private-first standards-oriented communications layer for WW.CX. IRC is the synchronous conversation plane. NNTP is the durable threaded discussion and archival plane. Both share local identity, authorization, storage, moderation policy, audit metadata, configuration validation, and operator tooling.

The implementation intentionally keeps public network exposure separate from software readiness. The repository contains protocol listeners and deployment assets, but its default configuration binds only to loopback laboratory ports and rejects non-loopback plaintext listeners.

## Components

```text
IRC clients                    NNTP clients
    |                              |
    v                              v
edge1_comms.irc                edge1_comms.nntp
    |                              |
    +------------+-----------------+
                 |
                 v
          edge1_comms.storage
          SQLite state/audit
                 |
       +---------+----------+
       |                    |
   commsctl             control API
                            |
                      read-only web UI
```

The production-oriented entry point is `server/edge1_commsd.py`, which hosts enabled IRC, NNTP, and HTTP control listeners in one supervised process so live IRC state can be exposed to the local read-only console without creating another privileged control socket. Standalone IRC and NNTP entry points remain available for laboratory testing.

## Identity and authorization

Accounts are local to the relay in version 0.1. Passwords are PBKDF2-HMAC-SHA256 hashes with per-account random salts. Plaintext credentials are never stored. The default iteration count is 240,000 and configuration validation refuses values below 100,000.

Roles are strings attached to accounts. `founder` is an override role. `moderator` and `moderator:<newsgroup>` authorize posting to moderated groups. Future integration can replace local credential verification behind the same account/policy boundary without changing IRC or NNTP protocol behavior.

IRC authentication uses SASL PLAIN over the IRCv3 capability negotiation flow. PLAIN is acceptable only when transported inside TLS for non-loopback service. The configuration validator therefore refuses non-loopback IRC without TLS.

NNTP uses `AUTHINFO USER` / `AUTHINFO PASS`. As with IRC, public exposure requires TLS at the listener.

## IRC capability

Implemented commands include:

- `CAP LS`, `CAP REQ`, `CAP END`;
- `AUTHENTICATE PLAIN`;
- `NICK`, `USER`, `PING`, `PONG`, `QUIT`;
- `JOIN`, `PART`, `PRIVMSG`, `NOTICE`;
- `TOPIC`, `NAMES`, `WHO`.

The server advertises `sasl`, `message-tags`, and `server-time` as capability names. Message-tag parsing is implemented. Expanded IRCv3 semantics and persistent channel modes remain versioned follow-up work.

IRC history is disabled by default. When enabled, channel joins and channel `PRIVMSG` events are stored. Direct/private-message contents are not persisted. Audit records store only metadata such as action, target, outcome, and byte counts; message bodies and credentials are excluded.

## NNTP capability

Implemented commands include:

- `CAPABILITIES`, `MODE READER`;
- `AUTHINFO USER`, `AUTHINFO PASS`;
- `LIST ACTIVE`, `LIST NEWSGROUPS`, `LIST OVERVIEW.FMT`;
- `GROUP`;
- `ARTICLE`, `HEAD`, `BODY`, `STAT`;
- `OVER` / `XOVER`;
- `NEXT`, `LAST`;
- `POST`, `QUIT`.

Initial groups are:

- `wwcx.general`;
- `wwcx.announce` (moderated);
- `wwcx.projects.bigbird`;
- `wwcx.projects.edge1`;
- `wwcx.telecom`;
- `wwcx.security` (moderated);
- `wwcx.test`.

Article Message-IDs are generated locally when absent. Existing valid Message-IDs may be preserved. Threading metadata uses `References`. Posting is text-first and limited by configurable line and article sizes.

Federation commands (`IHAVE`, `CHECK`, `TAKETHIS`) are explicitly denied in version 0.1. IRC server-to-server federation is likewise not present. Federation is a future, separately authorized feature rather than an accidental default.

## IRC to NNTP archival

When IRC history retention is enabled, an operator can archive a bounded recent channel transcript to an authorized NNTP group:

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json \
  archive channel '#edge1-dev' wwcx.projects.edge1 \
  'Edge1 development discussion' --author john --limit 100
```

The resulting article receives `X-WWCX-Archive-Source: irc:#edge1-dev`. This is operator initiated; automatic mirroring is not enabled.

## Storage

The SQLite database contains five durable areas:

- accounts;
- newsgroups;
- articles;
- optional IRC history;
- sanitized audit metadata.

NNTP article records are immutable through the network protocol. Administrative deletion/editing is intentionally not implemented in the initial operator CLI. That preserves a conservative evidence posture while moderation/retention governance is developed.

## Control API

The HTTP control surface is read-only and loopback-only by configuration policy. Endpoints:

```text
GET /api/comms/status
GET /api/comms/news/groups
GET /api/comms/audit?limit=100
```

Mutation methods return `405 read_only_control_api`. The browser UI under `src/web/comms-relay/` consumes only these endpoints.

## Configuration safety

The default example configuration uses:

```text
IRC      127.0.0.1:16667
NNTP     127.0.0.1:1119
Control  127.0.0.1:8099
```

These are laboratory/private-loopback ports. Intended standards-facing public endpoints are IRC/TLS `6697` and NNTP/TLS `563`, but changing listeners to non-loopback requires all of the following in configuration:

1. `network_exposure.enabled=true`;
2. TLS enabled on each public listener;
3. a certificate and key path configured.

The control HTTP service can never be configured for a non-loopback bind through the supported validator.

DNS, firewall policy, certificate issuance, authentication integration, public route changes, and external federation are outside the software implementation boundary and require separate operational authorization.

## Candidate configuration workflow

`commsctl` implements a durable candidate/running workflow:

```sh
bin/commsctl config validate candidate.json
bin/commsctl config diff /etc/wwcx/comms-relay.json candidate.json
bin/commsctl config stage candidate.json
sudo bin/commsctl config apply
```

Apply writes an atomic running configuration, creates a rollback backup when a prior file exists, and records that a service restart is required. It does not silently restart the service.

Rollback is explicit:

```sh
sudo bin/commsctl config rollback
```

The current running configuration is preserved as pre-rollback evidence before the previous backup is restored.

## Security invariants

- safe default is loopback-only;
- public plaintext protocol listeners are rejected by configuration validation;
- control API is loopback-only and read-only;
- authentication is required by default;
- anonymous posting is disabled;
- IRC history is disabled by default;
- NNTP federation is disabled;
- IRC federation is disabled;
- credentials and message bodies are excluded from audit metadata;
- systemd sandboxing removes capabilities and restricts writable paths to relay state;
- installation and service activation are separate actions.
