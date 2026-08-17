# WW.CX Edge1 Communications Relay Architecture

Status: accepted private production service  
Version: 1.0.0  
Last reconciled: 2026-08-17  
Protocols: IRC, local NNTP reader/poster, selective outbound NNTP ingestion, loopback read-only HTTP control/News Reader

## Purpose

Edge1 Communications Relay gives WW.CX a standards-oriented synchronous and durable discussion layer. IRC is the live conversation plane. NNTP is the durable threaded discussion and archival plane. Both share local identity, authorization, storage, moderation, retention and audit controls.

The relay also supports explicitly allowlisted outbound-only NNTP reader sources that import selected public Usenet groups into a separate local `usenet.*` namespace. Imported content remains clearly attributable to its upstream source and is not federation.

```text
IRC clients -----------------------> IRC service -----+
                                                       |
local NNTP clients ----------------> NNTP service ----+----> shared policy/storage -> SQLite WAL
                                                       |              |
Eternal September reader (TLS 563) -> ingestion ------+              +-> ingest ledger/cursors
                                                                      +-> commsctl
                                                                      +-> loopback control/API/UI
                                                                      +-> private News Reader
```

The unified production process is `server/edge1_commsd.py`. Standalone protocol entry points remain laboratory tools.

## Accepted network boundary

The accepted production listeners are loopback-only:

- IRC: `127.0.0.1:16667`;
- NNTP: `127.0.0.1:1119`;
- control/API/News Reader: `127.0.0.1:8100`.

Port `8099` remains assigned to the separate WW.CX telephony analytics API.

A non-loopback IRC or NNTP bind is rejected unless the separately gated exposure policy is explicitly enabled with TLS material. The control API remains loopback-only regardless.

The outbound Eternal September connections originate from the ingestion worker and do not add listeners.

## Security boundary

Runtime controls include:

- total and per-source connection ceilings;
- command token-bucket rate limits;
- failed-authentication throttling shared across reconnects from a source address;
- connection idle timeouts;
- bounded line and article sizes;
- PBKDF2-HMAC-SHA256 password hashes with random salts and per-account iteration metadata;
- minimum password length enforcement;
- server-side authenticated-user identity on native NNTP posts;
- denial of anonymous posts to moderated groups;
- explicit denial of NNTP federation commands;
- no IRC server-to-server implementation;
- TLS-required upstream NNTP reader connections;
- one explicitly configured upstream group per external source mapping;
- bounded external lookback, scan limit, article-size ceiling and global ingestion budget;
- credential-file references rather than credential values in repository configuration.

IRC SASL PLAIN and local NNTP AUTHINFO are permitted on loopback. Any separately authorized non-loopback protocol listener must use TLS.

## IRC

Version 1.0 implements CAP/SASL, NICK/USER registration, PING/PONG, JOIN/PART, PRIVMSG/NOTICE, TOPIC, NAMES, WHO, KICK and channel mode `+m`/`-m`. Founder, `moderator`, and `irc-operator` roles have operator authority. The server advertises only capabilities it implements (`sasl`).

IRC history is disabled by default. If enabled, channel joins and channel PRIVMSG events are retained for the configured interval; direct-message bodies are not persisted.

## Local NNTP

Version 1.0 implements CAPABILITIES, MODE READER, AUTHINFO USER/PASS, LIST variants, GROUP, ARTICLE/HEAD/BODY/STAT, OVER/XOVER, NEXT/LAST, POST and QUIT. `IHAVE`, `CHECK`, and `TAKETHIS` return a federation-disabled response.

Initial native groups are `wwcx.general`, `wwcx.announce`, `wwcx.projects.bigbird`, `wwcx.projects.edge1`, `wwcx.telecom`, `wwcx.security`, and `wwcx.test`. Announcement and security groups are moderated.

Authenticated native posts receive a canonical `username <username@users.ww.cx>` From identity plus `X-WWCX-Authenticated-User`. Imported articles do not impersonate native WW.CX posts; they use deterministic local Message-IDs and retain upstream provenance separately.

## Automatic ingestion

Automatic ingestion executes inside `edge1-comms-relay.service`; it does not add another daemon or listener. The accepted source order is:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

A per-database file lock prevents overlapping runs. Each source has a durable ledger identity and optional cursor in SQLite. A source failure is audited without stopping IRC, local NNTP, or the control surface.

### Local sources

- `wwcx-bootstrap` creates one stable introduction for groups it discovers.
- `edge1-repository` publishes eligible local Edge1 repository commits to `wwcx.projects.edge1`.

### Accepted outbound NNTP sources

- `comp.lang.python` -> `usenet.comp.lang.python` as `eternal.comp.lang.python`;
- `news.admin.peering` -> `usenet.news.admin.peering` as `eternal.news.admin.peering`.

Both use `news.eternal-september.org:563` with TLS required. Formal peering and the separate feeder service are not used.

## Article identity and provenance

For imported NNTP articles:

- upstream Message-ID is the source-item deduplication identity;
- WW.CX generates a deterministic local Message-ID;
- upstream author is preserved as displayed author;
- upstream server, group, Message-ID, article number, content type, date and references are stored in `X-WWCX-Upstream-*` headers when available;
- common `X-WWCX-Automated`, `X-WWCX-Source`, and `X-WWCX-Source-ID` headers remain present;
- SQLite `ingest_items` records source provenance and prevents duplicate source-item import.

A local imported group may also contain a legitimate `wwcx-bootstrap` introduction. Acceptance accounting is therefore provenance-aware, not based on raw total group count.

## Storage and retention

SQLite runs with foreign keys, busy timeout, WAL journal mode and normal synchronous durability. Each account stores the password-derivation iteration count used for its credential so future default changes do not invalidate existing accounts.

Retention is enforced at process startup and at a configured maintenance interval. Per-newsgroup article retention, IRC-history retention and audit retention are independent. The CLI also provides `maintenance prune` for explicit operator maintenance.

The live SQLite database is a restricted operational object. It can contain article bodies and local identity state and must not be committed to Git.

## Control surface and News Reader

The HTTP control service is read-only and loopback-only. Important endpoints include:

```text
GET /healthz
GET /api/comms/status
GET /api/comms/news/groups
GET /api/comms/news/groups/<group>
GET /api/comms/news/groups/<group>/articles
GET /api/comms/news/articles/<article-id>
GET /api/comms/news/sources
GET /api/comms/audit?limit=100
```

Mutation methods return HTTP 405 with `read_only_control_api`.

The private News Reader is served at `news.html` from the same control listener. It provides bounded search, source filters, pagination, article detail/provenance, and threaded/flat views based on stored reference ancestry. It contacts only the local relay database/API while browsing.

## Service readiness

`edge1-comms-relay.service` uses systemd `Type=simple`. A process can therefore be reported active before the Python control listener has completed initialization and bound its socket. Production restart verification must use a bounded readiness loop against `/healthz` and listener checks; `systemctl is-active` alone is not an application-readiness signal.

## Deployment and configuration model

The systemd unit uses a dedicated `wwcx-comms` identity, strict filesystem protection, no capabilities, restricted address families, namespace/realtime restrictions, process visibility restrictions, task/file-descriptor ceilings and memory ceilings.

Initial installation is dry-run-first and records protected deployment evidence. Later relay configuration changes use candidate validation, human-readable diff, stage/apply metadata, restart-required reporting and rollback. Apply/rollback preserves config ownership and mode.

The live News Reader production checkout is intentionally isolated from later unrelated remote `main` changes. Repository reconciliation does not authorize pulling unrelated work onto Edge1.

## Deliberate non-goals

The following remain separately gated and are not implied by the accepted service:

- public DNS/firewall/certificate provisioning for IRC/NNTP;
- Internet-facing IRC or NNTP listeners;
- IRC federation;
- inbound NNTP feeds;
- `IHAVE`, `CHECK`, `TAKETHIS` or streaming federation;
- formal bidirectional NNTP peering;
- upstream posting;
- forwarding private `wwcx.*` articles upstream;
- unrestricted anonymous posting;
- automatic mirroring of all upstream groups.

## Archive status

The current sanitized closeout is `docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`. Archive preparation is complete at the documentation level but not yet sealed; final sealing requires the protected host-side SHA-256 inventory and exact News Reader v2 evidence-path reconciliation.