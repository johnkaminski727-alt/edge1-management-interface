# Edge1 Communications Relay Upstream NNTP State

Date: 2026-08-16

## Objective

Add controlled outbound-only NNTP reader sources so Edge1 can selectively mirror explicitly allowlisted public Usenet groups into a separate local `usenet.*` namespace without enabling inbound peering, federation, or public listeners.

## Reference upstream

Eternal September is the initial reference provider.

Verified public technical state on 2026-08-15:

- reader hostname: `news.eternal-september.org`;
- TLS reader port: `563`;
- separate peering/transit hostname: `feeder.eternal-september.org`;
- peering/transit port: `433`;
- formal peering has operational prerequisites and is not part of this phase.

## Repository implementation state

The selective outbound NNTP implementation is merged. The validated implementation floor is:

`c7b4b2c9124e072abaa356f0645e10d449c38eea`

Implemented behavior includes:

- `nntp` ingestion source type;
- TLS required for upstream reader connections;
- one upstream group to one local group mapping per source;
- optional automatic creation of only the explicitly configured local group;
- credential-file reference rather than credential values in relay configuration;
- sanitized config exposes only whether a credential file is configured;
- bounded initial lookback, scan limit, per-run budget, article byte ceiling, and retention;
- single-part `text/*` article acceptance only;
- upstream Message-ID deduplication;
- deterministic WW.CX local Message-ID;
- upstream author and provenance headers preserved;
- article-number cursor with bounded reset/rewrite recovery;
- scripted no-network protocol validation for AUTHINFO/GROUP/ARTICLE parsing;
- example disabled Eternal September source;
- operator/design documentation.

## Live state

Selective Eternal September ingestion is accepted live on Edge1 for two explicit mappings.

Live Edge1 checkout for the second-source acceptance:

`40004fdb4ab034c0ae3051be69df8c83e9db7f61`

Accepted sources:

### `eternal.comp.lang.python`

- upstream: `news.eternal-september.org:563`;
- upstream group: `comp.lang.python`;
- local target: `usenet.comp.lang.python`;
- TLS required;
- credential file: `/etc/wwcx/credentials/eternal-september.json`;
- credential metadata observed as `root:wwcx-comms` mode `0640`;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial window: 8;
- scan ceiling: 10;
- scheduled through the existing 900-second relay ingestion cycle.

### `eternal.news.admin.peering`

- upstream: `news.eternal-september.org:563`;
- upstream group: `news.admin.peering`;
- local target: `usenet.news.admin.peering`;
- TLS required;
- uses the same protected local credential file;
- retention: 3650 days;
- maximum article size: 262144 bytes;
- initial window: 8;
- scan ceiling: 10;
- scheduled through the existing 900-second relay ingestion cycle.

The accepted automatic source order is:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

Acceptance records:

- first source: `docs/communications/edge1-comms-relay-upstream-nntp-live-acceptance-20260815.md`;
- second source: `docs/communications/edge1-comms-relay-upstream-nntp-live-acceptance-20260816.md`.

Final second-source evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`

## Accepted data state

`usenet.comp.lang.python` contains two legitimate provenance classes:

- 8 articles from `eternal.comp.lang.python`;
- 1 normal one-time introduction from `wwcx-bootstrap` with source item ID `usenet.comp.lang.python:v1`.

`usenet.news.admin.peering` likewise contains:

- 8 articles from `eternal.news.admin.peering`;
- 1 normal one-time introduction from `wwcx-bootstrap` with source item ID `usenet.news.admin.peering:v1`.

For both external sources, duplicate source IDs were verified as zero. The second-source acceptance additionally verified zero orphan ledger rows, wrong-group rows, unexpected provenance rows, bad/mismatched NNTP provenance rows, and ingestion errors since activation. Its live cursor was present at article number `3748`.

Validation must remain provenance-aware. Do not require the total article count of an imported local group to equal the external source ledger count when another approved source, such as `wwcx-bootstrap`, also posts to that group.

## Operational lesson: service readiness

The relay systemd unit is `Type=simple`. A successful `systemctl restart` plus `active` state can precede the control listener becoming reachable for a brief interval.

Production activation wrappers must therefore use a bounded `/healthz` readiness loop after restart rather than a one-shot immediate probe. During the second-source activation, the original one-shot probe triggered a safe automatic rollback before any second-source data was ingested; the corrected retry passed readiness on attempt 2 and was then fully accepted.

## Safety boundaries

The live sources are outbound reader-pull only.

Still disabled or separately gated:

- upstream posting;
- inbound NNTP feeds;
- server-to-server streaming;
- formal bidirectional peering;
- `feeder.eternal-september.org` use;
- DNS or firewall changes for the relay;
- certificate changes for the relay;
- public Edge1 IRC/NNTP exposure;
- forwarding private WW.CX articles upstream.

Additional public groups must be added as separate explicit allowlisted mappings and validated incrementally.
