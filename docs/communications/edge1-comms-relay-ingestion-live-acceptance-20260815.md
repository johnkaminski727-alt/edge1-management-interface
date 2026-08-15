# Edge1 Communications Relay Automatic Ingestion Live Acceptance

Date: 2026-08-15  
Host: `edge1.ww.cx`  
Activation time: approximately 19:19 UTC  
Deployed repository revision: `359eb977cd8bcc4c986fe688b934303cb53c23d6`  
Service: `edge1-comms-relay.service`

## Outcome

Controlled automatic NNTP article ingestion is accepted as live on the private WW.CX Edge1 Communications Relay.

The accepted automatic sources are:

- `wwcx-bootstrap`: stable introduction articles for the existing seven `wwcx.*` groups;
- `edge1-repository`: local `/opt/edge1-management-interface` `main` history into `wwcx.projects.edge1`.

The scheduled ingestion interval is 900 seconds (15 minutes), with a five-second startup delay and a 25-item per-run budget.

External RSS/Atom feeds, NNTP peering, IRC federation, public listeners, automatic IRC-to-NNTP mirroring, DNS changes, firewall changes, and certificate changes remain disabled or unconfigured.

## Safety preparation

Before enabling ingestion, the attended Edge1 session verified:

- the validated relay revision remained an ancestor of the fetched `main` revision;
- later repository changes did not touch protected communications-relay paths;
- `tests/validate_comms_relay.py` passed;
- `tests/validate_comms_ingest.py` passed;
- `tests/validate_comms_config_control_metadata.py` passed;
- the running relay was healthy and active;
- the running config remained `root:wwcx-comms` mode `0640`;
- ingestion was absent from the running config;
- a consistent pre-change SQLite backup was captured.

Pre-change evidence root:

`/var/lib/wwcx-deployment-evidence/comms-relay/auto-ingest-20260815T191918Z`

Pre-change database backup:

`/var/lib/wwcx-deployment-evidence/comms-relay/auto-ingest-20260815T191918Z/comms.sqlite3.before`

The backup SHA-256 recorded during activation was:

`b9b6dffa5639fb86dfaa5246d4bc980cc68ef4193ea2ff1f198c981620a386a5`

The code deployment with the old ingestion-disabled config also passed the bundled relay smoke test. Installer evidence:

`/var/lib/wwcx-deployment-evidence/comms-relay/20260815T191922Z`

## Candidate configuration acceptance

The ingestion candidate validated successfully and added only the controlled ingestion section. The candidate was staged and applied through the relay candidate/running configuration workflow.

The apply record verified preservation of the running config metadata:

- UID: `0`;
- GID: `985` at activation time;
- mode: `0640`;
- ownership observed before and after: `root:wwcx-comms`.

A config-control backup was created at:

`/var/lib/wwcx-comms/config-control/backups/comms-relay.20260815T191924Z.json`

## Automatic population result

The live dry run predicted 15 initial candidates:

- 7 bootstrap/group-introduction articles;
- 8 recent local Edge1 repository commit articles.

After relay restart, the automatic startup ingestion reached exactly 15 ledger items. The first live ingestion audit recorded `created: 15`, `deduplicated: 0`, `sources: 2`, outcome `ok`.

The resulting group counts included:

- `wwcx.announce`: 1;
- `wwcx.general`: 1;
- `wwcx.projects.bigbird`: 1;
- `wwcx.projects.edge1`: 9 (one group introduction plus eight repository articles);
- `wwcx.security`: 1;
- `wwcx.telecom`: 1;
- `wwcx.test`: 1.

All 15 generated articles were inspected against the ingestion ledger and verified to carry:

- `X-WWCX-Automated: yes`;
- matching `X-WWCX-Source`;
- matching `X-WWCX-Source-ID`;
- deterministic ingest Message-IDs under `edge1.ww.cx`.

An immediate second ingestion run found zero candidates and created zero articles, confirming idempotent deduplication after the initial live population.

## Runtime verification

After ingestion was enabled:

- `edge1-comms-relay.service` remained enabled and active;
- the bundled IRC/NNTP/control smoke test passed;
- IRC remained loopback-only on `127.0.0.1:16667`;
- NNTP remained loopback-only on `127.0.0.1:1119`;
- relay control remained loopback-only on `127.0.0.1:8100`;
- existing telephony analytics remained healthy on `127.0.0.1:8099`;
- relay `/healthz` returned service `edge1-comms-relay`, status `ok`, version `1.0.0`;
- no public network exposure was introduced.

## Accepted operating state

Automatic NNTP population is active and will check the configured local Edge1 repository source every 15 minutes. New eligible `main` commits are posted into `wwcx.projects.edge1` with provenance and deduplication state.

Bootstrap items are stable one-time source IDs and are not recreated on later runs.

This acceptance does not authorize or enable arbitrary Internet content ingestion. Additional source types or external feed endpoints remain separately reviewed and governed changes.
