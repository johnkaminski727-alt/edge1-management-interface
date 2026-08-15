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

Feature branch: `feature/comms-relay-upstream-nntp-pull`.

Implemented on the branch:

- new `nntp` ingestion source type;
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

No external NNTP source is enabled on Edge1 by this branch. Existing live automatic sources remain `wwcx-bootstrap` and `edge1-repository` only.

No account was created with Eternal September, no credentials were generated or stored, no peering request was sent, and no DNS/firewall/listener/certificate change was made.

## Activation gate

Live upstream activation remains blocked until an operator legitimately creates reader credentials outside the repository, installs them in a protected Edge1 credential file, selects the exact allowlisted groups, and performs the documented backup/candidate/dry-run/health verification sequence.

Formal bidirectional NNTP peering is explicitly out of scope for this phase.
