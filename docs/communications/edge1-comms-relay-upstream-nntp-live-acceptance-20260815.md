# Edge1 Communications Relay Eternal September Upstream NNTP Live Acceptance

Date: 2026-08-15  
Host: `edge1.ww.cx`  
Activation time: approximately 23:34 UTC  
Live Edge1 checkout revision: `ffd086389c5c8687c33afae6c072a4ca1972f9b3`  
Service: `edge1-comms-relay.service`

## Outcome

Selective outbound-only NNTP ingestion from Eternal September is accepted as live on the private WW.CX Edge1 Communications Relay.

Accepted source mapping:

- source name: `eternal.comp.lang.python`;
- upstream reader: `news.eternal-september.org:563`;
- TLS: required and previously verified with authenticated live reader access;
- upstream group: `comp.lang.python`;
- local group: `usenet.comp.lang.python`;
- local retention: 3650 days;
- maximum upstream article size: 262144 bytes;
- initial item window: 8;
- per-source scan ceiling: 10;
- scheduled ingestion interval: existing relay 900-second / 15-minute cycle.

The credential file remains outside the repository at `/etc/wwcx/credentials/eternal-september.json` with observed ownership `root:wwcx-comms` and mode `0640`. No credential values are recorded in repository evidence.

## Scope boundaries

This acceptance enables only outbound reader-pull ingestion for the allowlisted group above.

The following remain disabled or out of scope:

- upstream posting;
- `IHAVE`, `CHECK`, `TAKETHIS`, or other server-to-server feed commands;
- inbound NNTP feeds;
- formal Eternal September peering;
- public IRC or NNTP relay listeners;
- DNS changes;
- firewall changes;
- certificate changes for the relay.

## Repository and implementation validation

Immediately before final activation, the attended Edge1 session froze the clean local `main` checkout at:

`ffd086389c5c8687c33afae6c072a4ca1972f9b3`

The validated upstream-NNTP implementation merge `c7b4b2c9124e072abaa356f0645e10d449c38eea` was confirmed as an ancestor of that checkout. Later changes between the feature merge and the live checkout did not touch protected Communications Relay implementation, deployment, configuration, or validation paths.

The following targeted validations passed on the live checkout:

- `tests/validate_comms_relay.py`;
- `tests/validate_comms_ingest.py`;
- `tests/validate_comms_upstream_nntp.py`;
- `tests/validate_comms_config_control_metadata.py`.

## Prior authenticated dry-run acceptance

Before live activation, an attended real-network dry run against `news.eternal-september.org:563` verified:

- TLS connection and certificate validation;
- reader authentication using the protected local credential file;
- access to `comp.lang.python`;
- eight eligible upstream article candidates;
- zero skipped candidates in the sampled window;
- zero database mutation;
- unchanged relay health.

The initial real import then created eight Eternal September source-ledger items. A later WW.CX bootstrap cycle detected the newly created local group and added its normal one-time `Welcome to usenet.comp.lang.python` introduction article.

## Provenance-aware article accounting

The accepted local group state is intentionally not equal to the Eternal September ledger count.

At final activation the verified counts were:

- Eternal September articles: 8;
- WW.CX bootstrap introductions: 1;
- duplicate Eternal September source IDs: 0.

Therefore the local group contains one more article than the external source ledger because `wwcx-bootstrap` creates a one-time introduction for every newly discovered local group.

Operational validation must classify local-group articles by `source_name` / source provenance rather than require `group_article_count == external_source_ledger_count`.

The bootstrap introduction is identified by:

- source: `wwcx-bootstrap`;
- source item ID: `usenet.comp.lang.python:v1`.

## Final activation evidence

Final evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-september-live-20260815T233435Z`

The final attended activation created fresh pre-change backups before applying the candidate.

Recorded SHA-256 values:

- pre-change live config: `62689ceb35352bd92c5ab7b9922a1f32400ff43149ea13f61148d008ccbdb16d`;
- pre-change SQLite backup: `0efa60cdc528943bb509e490f925c843cdae04521eb907b4561aab18283d9989`.

The candidate added only the reviewed `eternal.comp.lang.python` source between `wwcx-bootstrap` and `edge1-repository`.

Config-control staging and apply completed successfully. The running config preserved:

- owner: `root`;
- group: `wwcx-comms`;
- mode: `0640`.

## Runtime verification

After the final candidate was applied and the relay restarted:

- `edge1-comms-relay.service` was active;
- the bundled Communications Relay smoke test passed;
- `/healthz` returned service `edge1-comms-relay`, status `ok`, version `1.0.0`;
- the Eternal September source was present and enabled in the persistent live config;
- an attended live ingestion run completed with zero new candidates and zero new creations for all three configured sources;
- Eternal September source IDs remained unique;
- the eight preserved upstream articles remained present;
- the WW.CX bootstrap introduction remained present;
- Communications Relay listeners remained loopback-only;
- the service remained enabled and active.

The zero-candidate attended run is expected because the upstream cursor had already advanced through the accepted initial eight-article window and no newer eligible article was available at that instant.

## Accepted operating state

The live automatic sources are now:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `edge1-repository`.

Eternal September is a bounded selective reader source only. Native private `wwcx.*` groups remain separate from imported public groups under the `usenet.*` namespace.

Formal bidirectional NNTP peering remains a separate future project with separate network, abuse-control, moderation, feed-protocol, and operational approval requirements.
