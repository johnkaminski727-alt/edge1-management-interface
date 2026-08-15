# Edge1 Communications Relay Upstream NNTP State

Date: 2026-08-15

## Objective

Add a controlled outbound-only NNTP reader source so Edge1 can selectively mirror explicitly allowlisted public Usenet groups into a separate local `usenet.*` namespace without enabling inbound peering, federation, or public listeners.

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

Selective Eternal September ingestion is accepted live on Edge1 as of approximately 23:34 UTC on 2026-08-15.

Live Edge1 checkout at acceptance:

`ffd086389c5c8687c33afae6c072a4ca1972f9b3`

Accepted source:

- source name: `eternal.comp.lang.python`;
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

The accepted automatic source order is:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `edge1-repository`.

Final evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z`

Live acceptance record:

`docs/communications/edge1-comms-relay-upstream-nntp-live-acceptance-20260815.md`

## Accepted data state

The imported local group contains two legitimate provenance classes:

- 8 articles from `eternal.comp.lang.python`;
- 1 normal one-time introduction from `wwcx-bootstrap` with source item ID `usenet.comp.lang.python:v1`.

Duplicate Eternal September source IDs were verified as zero.

Validation must therefore be provenance-aware. Do not require the total article count of an imported local group to equal the external source ledger count when another approved source, such as `wwcx-bootstrap`, also posts to that group.

## Safety boundaries

The live source is outbound reader-pull only.

Still disabled or separately gated:

- upstream posting;
- inbound NNTP feeds;
- server-to-server streaming;
- formal bidirectional peering;
- DNS or firewall changes for the relay;
- public Edge1 IRC/NNTP exposure;
- forwarding private WW.CX articles upstream.

Additional public groups must be added as separate explicit allowlisted mappings and validated incrementally.
