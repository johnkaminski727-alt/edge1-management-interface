# Edge1 Communications Relay Automatic Ingestion

Status: accepted live production behavior  
Last reconciled: 2026-08-17

## Purpose

Automatic ingestion gives the private WW.CX NNTP service useful durable content without enabling NNTP federation or an unrestricted Internet feed. The relay converts explicitly configured sources into NNTP articles, records provenance on every generated/imported article, and keeps a durable source-item ledger so repeated runs cannot duplicate content.

## Accepted source order

The current accepted source order is:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

The order matters operationally because `wwcx-bootstrap` creates a one-time introduction only for groups that exist when its source pass runs. A newly auto-created imported group can therefore receive its bootstrap introduction on a subsequent ingestion cycle.

## Source types

### `bootstrap`

Creates one stable introduction article in each configured/discovered group using local group metadata. Source-item identity is `<group>:v1`.

### `git`

Watches the root-controlled local `/opt/edge1-management-interface` repository and publishes eligible commits to `wwcx.projects.edge1`.

### `nntp`

Uses an outbound TLS reader connection to pull one explicitly configured upstream group into one explicitly configured local `usenet.*` group. It does not enable inbound feeds, server-to-server streaming, public listeners, or upstream posting.

Accepted Eternal September mappings:

- `eternal.comp.lang.python`: `comp.lang.python` -> `usenet.comp.lang.python`;
- `eternal.news.admin.peering`: `news.admin.peering` -> `usenet.news.admin.peering`.

Both use `news.eternal-september.org:563` with TLS required and the existing protected credential file reference. The credential values are never part of the relay JSON, logs, repository, or archive documentation.

## Provenance and deduplication

All ingested articles receive common WW.CX provenance:

- deterministic local Message-ID derived from source name plus source-item identity;
- `X-WWCX-Automated: yes`;
- `X-WWCX-Source`;
- `X-WWCX-Source-ID`.

Git articles also preserve commit/source metadata.

Imported NNTP articles additionally preserve upstream metadata in `X-WWCX-Upstream-*` headers when available, including server, group, Message-ID, article number, content type, date and references.

For NNTP sources, the upstream Message-ID is the ingestion source-item ID and deduplication identity. Upstream article renumbering therefore does not by itself create a duplicate local article.

SQLite tables `ingest_items` and `ingest_state` retain deduplication state and per-source cursors. Article retention may remove an old article while leaving its ingest ledger record, preventing accidental re-import of expired source items.

## Provenance-aware accounting

Do not validate an imported local group by comparing its total article count with only the external-source ledger.

A legitimate `wwcx-bootstrap` introduction can coexist in the same group. The accepted initial states demonstrate this:

- `usenet.comp.lang.python`: 8 `eternal.comp.lang.python` items + 1 bootstrap introduction;
- `usenet.news.admin.peering`: 8 `eternal.news.admin.peering` items + 1 bootstrap introduction.

For acceptance, validate:

- source-specific `ingest_items` count;
- unique `source_item_id` values;
- target-group membership;
- source/provenance headers;
- cursor state where applicable;
- explicitly understood non-external provenance classes;
- duplicate, orphan and unexpected-provenance counts.

## Runtime behavior

Ingestion runs inside `edge1-comms-relay.service`; it does not add a listener or second daemon. The accepted scheduler uses:

- startup delay: 5 seconds;
- interval: 900 seconds;
- total run budget: 25 items.

A per-database file lock prevents overlapping ingestion runs. A manual run that collides with the scheduled worker reports `already_running` rather than running concurrently.

A source failure is audited by error type and does not stop IRC, local NNTP, or the read-only control/News Reader service.

## Accepted NNTP source bounds

For both currently accepted Eternal September sources:

- TLS: required;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial items: 8;
- scan limit: 10.

The adapter accepts only bounded single-part `text/*` articles with valid upstream Message-ID values.

## Operator controls

Use the explicit live config path:

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json ingest status
bin/commsctl --config /etc/wwcx/comms-relay.json ingest run --dry-run
sudo -u wwcx-comms bin/commsctl --config /etc/wwcx/comms-relay.json ingest run
```

A successful dry run returns candidate information without creating groups/articles or writing cursor/ingest state.

If a manual run reports `already_running`, wait for the scheduled run to complete and retry rather than bypassing the ingestion lock.

## Security boundary

Git execution uses an argument vector rather than a shell, a fixed `/usr/bin/git` binary, restricted environment, root-controlled absolute repository path, validated ref and explicit read-only `safe.directory` override.

Outbound NNTP uses normal TLS certificate/hostname verification. The credential file is read internally by the source implementation and its values must never be printed or copied into evidence.

Automatic ingestion does not alter:

- listener addresses;
- authentication policy;
- DNS;
- firewall rules;
- TLS certificates;
- federation state;
- telephony services.

## Live acceptance references

- local automatic ingestion: `edge1-comms-relay-ingestion-live-acceptance-20260815.md`;
- first Eternal September source: `edge1-comms-relay-upstream-nntp-live-acceptance-20260815.md`;
- second Eternal September source: `edge1-comms-relay-upstream-nntp-second-source-live-acceptance-20260816.md`.

## Future sources

Additional public NNTP groups may be added only as separate explicit one-group mappings and validated incrementally. Curated RSS/Atom, Big Bird status/release sources, telecom notices, security advisories, and selected IRC digests remain future source types requiring their own trust policy, bounded fetch behavior, provenance, deduplication and live activation review.

Formal NNTP peering is not a future-source shortcut; it is a separate architecture and authorization project.
