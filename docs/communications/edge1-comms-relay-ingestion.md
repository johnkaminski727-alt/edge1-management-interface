# Edge1 Communications Relay Automatic Ingestion

Status: repository implementation pending live activation  
Date: 2026-08-15

## Purpose

Automatic ingestion gives the private WW.CX NNTP service useful durable content without enabling Usenet federation or an unrestricted Internet feed. The relay converts explicitly configured trusted local sources into NNTP articles, records provenance on every generated article, and keeps a durable source-item ledger so a repeated run cannot duplicate content.

## Shipping sources

The initial production configuration contains two source types:

- `bootstrap`: creates one stable introduction article in each configured `wwcx.*` newsgroup using the local group description, moderation flag, and retention setting;
- `git`: watches the local `/opt/edge1-management-interface` `main` history and publishes repository changes to `wwcx.projects.edge1`.

No RSS/Atom URL, arbitrary web source, IRC mirroring, NNTP peer, or external news provider is enabled by this implementation.

## Provenance and deduplication

Every generated article receives:

- a deterministic Message-ID derived from source name plus source-item ID;
- `X-WWCX-Automated: yes`;
- `X-WWCX-Source`;
- `X-WWCX-Source-ID`;
- a source-type header;
- for Git articles, the commit ID and configured HTTPS source URL.

SQLite tables `ingest_items` and `ingest_state` retain deduplication state and per-source cursors. Article retention may remove an old article while leaving its ingest ledger record, so expired source items are not unexpectedly re-created.

## Runtime behavior

Ingestion runs inside `edge1-comms-relay.service`; it does not add a listener or a second daemon. When enabled, the worker waits for the configured startup delay, performs one run, then repeats at the configured interval. A per-database file lock prevents overlapping ingestion runs.

An ingestion-source failure is audited by error type and does not stop IRC, NNTP, or the read-only control API.

The example production policy is:

- startup delay: 5 seconds;
- interval: 900 seconds;
- total run budget: 25 items;
- initial Edge1 Git lookback: 8 commits;
- Git rewrite recovery scan: 500 commits.

## Operator controls

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json ingest status
bin/commsctl --config /etc/wwcx/comms-relay.json ingest run --dry-run
sudo -u wwcx-comms bin/commsctl --config /etc/wwcx/comms-relay.json ingest run
```

The dry run lists candidate source items without creating articles, changing cursors, or writing ingest state.

## Security boundary

Git execution uses an argument vector rather than a shell, a fixed `/usr/bin/git` binary, a restricted environment, a root-controlled absolute repository path, a strictly validated ref, and an explicit read-only `safe.directory` override for the configured path. Optional source links must be credential-free HTTPS URLs.

Automatic ingestion does not alter listener addresses, authentication policy, DNS, firewall rules, TLS certificates, federation state, or telephony services.

## Future source types

Curated RSS/Atom sources, Big Bird release/status sources, telecom notices, security advisories, and selected IRC digests can be added behind the same source ledger. Each new external source type requires explicit URL/trust policy, bounded fetch behavior, content-size limits, provenance, deduplication, and separate live activation review.
