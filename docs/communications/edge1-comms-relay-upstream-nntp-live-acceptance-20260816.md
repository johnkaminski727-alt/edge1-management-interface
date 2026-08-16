# Edge1 Communications Relay Eternal September `news.admin.peering` Live Acceptance

Date: 2026-08-16  
Host: `edge1.ww.cx`  
Production activation: 00:51 UTC  
Live Edge1 checkout revision: `40004fdb4ab034c0ae3051be69df8c83e9db7f61`  
Validated implementation floor: `c7b4b2c9124e072abaa356f0645e10d449c38eea`  
Service: `edge1-comms-relay.service`

## Outcome

A second explicit Eternal September reader-pull source is accepted live on the private WW.CX Edge1 Communications Relay.

Accepted mapping:

- source name: `eternal.news.admin.peering`;
- upstream reader: `news.eternal-september.org:563`;
- TLS: required;
- upstream group: `news.admin.peering`;
- local group: `usenet.news.admin.peering`;
- local retention: 3650 days;
- maximum upstream article size: 262144 bytes;
- initial item window: 8;
- per-source scan ceiling: 10;
- scheduled ingestion interval: existing relay 900-second / 15-minute cycle.

The existing protected Eternal September credential file remains outside the repository at `/etc/wwcx/credentials/eternal-september.json`. Only its metadata was verified: owner `root`, group `wwcx-comms`, mode `0640`. No credential values are recorded here or in deployment evidence intended for repository use.

## Pre-activation soak and dry-run

Before the second source was activated, the existing `eternal.comp.lang.python` production source passed a read-only soak check at frozen checkout `40004fdb4ab034c0ae3051be69df8c83e9db7f61`:

- service enabled and active;
- `/healthz` healthy;
- listeners limited to loopback on ports 16667, 1119, and 8100;
- existing source cursor present;
- duplicate external source IDs: 0;
- ingestion errors since prior activation: 0;
- existing accepted data preserved as 8 external articles plus 1 `wwcx-bootstrap` introduction;
- targeted relay validation scripts passed;
- protected relay implementation paths were unchanged from the validated implementation floor.

A protected candidate adding only `eternal.news.admin.peering` was then built and validated. The attended real-network dry-run against Eternal September verified:

- authenticated TLS reader access using the protected local credential file;
- access to `news.admin.peering`;
- 8 eligible article candidates;
- 8 scanned and 0 skipped;
- all accepted candidates were `text/plain` and within the configured article-size bound;
- all candidates mapped to `usenet.news.admin.peering` with the expected NNTP provenance headers;
- no new local group, cursor, source-ledger item, or other ingestion database mutation occurred during dry-run.

Dry-run preparation evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-prep-20260816T001246Z`

Accepted candidate SHA-256 before config-control canonicalization:

`86569e2085be9569e5fb5715556c9b88927502928bd9e486d9f960f666889697`

## Activation readiness lesson

The first attended activation attempt at approximately 00:20 UTC applied the reviewed candidate and restarted only `edge1-comms-relay.service`, but the acceptance wrapper probed `/healthz` immediately after `systemctl restart` and received a transient connection refusal.

The wrapper automatically rolled the running configuration back to the prior accepted configuration and restarted the relay. Follow-up inspection showed:

- the prior configuration was restored;
- the relay was enabled, active, and healthy;
- all three listeners were loopback-only;
- no `usenet.news.admin.peering` group, source items, cursor, or bootstrap introduction had been created;
- a normal scheduled ingestion run completed after rollback.

This was classified as an acceptance-script readiness race rather than a relay configuration failure. The systemd unit is `Type=simple`, so active process state does not by itself prove that the control listener is already accepting connections. The activation retry therefore used a bounded readiness loop for `/healthz` instead of a one-shot immediate probe.

## Final activation

The final activation began at approximately 00:51 UTC on 2026-08-16.

Fresh pre-change configuration and SQLite backups were created before staging and applying the already accepted candidate. Config-control staging and apply succeeded, preserving the running configuration metadata as `root:wwcx-comms` mode `0640`.

Only `edge1-comms-relay.service` was restarted. The bounded health check succeeded on attempt 2. Runtime verification then confirmed:

- service enabled and active;
- `/healthz` returned `status: ok`, service `edge1-comms-relay`, version `1.0.0`;
- listeners remained loopback-only on `127.0.0.1:16667`, `127.0.0.1:1119`, and `127.0.0.1:8100`;
- the new source was present in the live configuration;
- public network exposure remained disabled;
- configuration and credential-file metadata remained `root:wwcx-comms` mode `0640`.

Final activation evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/eternal-news-admin-peering-live-20260816T005124Z`

## Accepted data and provenance state

The first live automatic ingestion for the new source completed at 00:51:34 UTC and created 8 `eternal.news.admin.peering` articles. The source cursor advanced to article number `3748`.

A later normal `wwcx-bootstrap` cycle created the one-time local introduction `usenet.news.admin.peering:v1`. A subsequent scheduled run created no additional items.

Final provenance-aware acceptance verified:

- `eternal.news.admin.peering` articles in `usenet.news.admin.peering`: 8;
- `wwcx-bootstrap` introduction in `usenet.news.admin.peering`: 1;
- orphan new-source ledger rows: 0;
- wrong-group new-source rows: 0;
- duplicate new-source IDs: 0;
- unexpected provenance rows: 0;
- bad/mismatched stored NNTP provenance rows: 0;
- new-source cursor present: yes;
- ingestion errors since final activation: 0.

The previously accepted Python mirror remained intact:

- `eternal.comp.lang.python` articles in `usenet.comp.lang.python`: 8;
- `wwcx-bootstrap` introduction `usenet.comp.lang.python:v1`: 1;
- duplicate `eternal.comp.lang.python` source IDs: 0.

Accepted local provenance counts are therefore:

- `usenet.comp.lang.python` / `eternal.comp.lang.python`: 8;
- `usenet.comp.lang.python` / `wwcx-bootstrap`: 1;
- `usenet.news.admin.peering` / `eternal.news.admin.peering`: 8;
- `usenet.news.admin.peering` / `wwcx-bootstrap`: 1.

## Accepted operating state

The live automatic source order is now:

1. `wwcx-bootstrap`;
2. `eternal.comp.lang.python`;
3. `eternal.news.admin.peering`;
4. `edge1-repository`.

Both Eternal September mappings are bounded selective outbound reader sources. Imported public groups remain under the local `usenet.*` namespace and remain distinct from private native `wwcx.*` groups.

## Scope boundaries preserved

This acceptance did not enable or modify:

- upstream posting;
- `IHAVE`, `CHECK`, `TAKETHIS`, or other server-to-server streaming/feed commands;
- inbound NNTP feeds;
- formal Eternal September peering or `feeder.eternal-september.org`;
- DNS;
- firewall rules;
- certificates;
- public IRC or NNTP listener exposure;
- forwarding private `wwcx.*` articles upstream.

Additional public groups remain individually allowlisted changes requiring their own bounded validation and production acceptance.
