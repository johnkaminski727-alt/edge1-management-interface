# WW.CX Unified Communications — Live Acceptance Record

Date: 2026-08-19
Host: `edge1.ww.cx`
Operator principal: `wwadmin`
Accepted repository head: `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`
Protected evidence root: `/var/tmp/wwcx-uc-live-20260819T024027Z`

## Result

The approved safe-scope Unified Communications live objective is **accepted**.

This acceptance covers:

- private MMS quarantine with live local trusted scanning;
- local-native Mail Room RFC822 persistence/read/thread behavior;
- dedicated `wwcx-private-ai` authenticated Mail correspondence access;
- BigBird Mail status/correspondence/prepared-draft integration;
- fresh shared regression of adjacent UC services and private listeners.

This acceptance does **not** authorize production SMS/MMS/email transmission, call origination, carrier/emergency routing changes, provider activation, quarantine release, or other separately protected actions.

## Repository corrections discovered during live work

### PR #444 — MMS directory privacy

Live inspection revealed that intermediate quarantine directories (`blobs`, `metadata`, `scan-state`) could be created as mode `0755` because `Path.mkdir(parents=True, mode=0o700)` does not apply the requested mode to missing parent components.

The live tree was immediately tightened to `0700` directories / `0600` files. Repository code and regression coverage were updated and merged as:

- head: `9527f65692102887d0557ad20ebe816af9d5f05b`;
- merge: `28534e81396418b063006897248acba9c51af282`.

The corrected module was deployed to `/opt/wwcx-messaging-gateway-staging` and its hash matched the reviewed repository.

### PR #445 — Mail runtime correspondence wiring

Live path review found that the deployed Mail service runs `outbound_mail_gateway_runtime_server.py` / `RuntimeGatewayApplication`, while correspondence methods were only exposed through the non-runtime application path.

The runtime application was wired to correspondence status/message/thread operations with regression validation and merged as:

- head: `2a5bca36494eaa7b51759d371d83fe5b17420e34`;
- merge: `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`.

All exact-head checks passed before merge.

## MMS acceptance

Service:

- unit: `wwcx-messaging-gateway.service`;
- identity: `wwadmin:wwadmin`;
- listener: `127.0.0.1:58080`;
- sandbox retains `ProtectSystem=strict` with a narrow writable allowance for the private quarantine root.

Scanner:

- `/usr/bin/clamscan` installed;
- ClamAV version observed: `1.4.3`;
- daily signature DB updated to version `28096`;
- no `clamd` listener on port 3310;
- upstream warning recommends ClamAV 1.4.6, recorded as maintenance follow-up only.

Private root:

`/var/lib/wwcx-messaging-gateway/private-mms-quarantine`

Verified:

- all directories mode `0700`;
- all files mode `0600`;
- clean fixture -> `scanned_clean_held`;
- EICAR fixture -> `quarantined_malicious`;
- restart recovery -> held;
- `release_authorized=false`;
- fresh-tree permission regression passed;
- service restart and `/healthz` passed;
- no public scanner listener introduced.

## Local Mail Room acceptance

Service:

- unit: `wwcx-outbound-mail-gateway.service`;
- identity: `wwcx-mail-gateway:wwcx-mail-gateway`;
- listener: `127.0.0.1:8104`;
- actual runtime entry point: `server/outbound_mail_gateway_runtime_server.py`.

Private store:

- `/var/lib/wwcx-mail-room` mode `0700`;
- `/var/lib/wwcx-mail-room/correspondence.sqlite3` mode `0600`;
- owner `wwcx-mail-gateway`.

Two RFC822 fixtures were ingested:

- `<local-root@example.test>`;
- `<local-reply@example.test>`.

Both persisted with:

- source `local-mailroom-rfc822`;
- scope `local_native`;
- authoritative `true`;
- identical explicit thread ID;
- `content_is_untrusted=true`;
- `send_authorized=false`;
- `mutation_authorized=false`.

Authentication and API acceptance:

- `wwcx-private-ai` added to deployed allowed clients while retaining `wwcx-website-admin`;
- existing HMAC secret mechanism reused without disclosure or rotation;
- unsigned correspondence -> HTTP 401;
- website-admin correspondence -> HTTP 401;
- private-ai correspondence status -> `ready_local_native`;
- `production_provider_ready=false`;
- individual message read -> pass;
- thread read count 2 -> pass;
- prompt-like body retained as untrusted data;
- malformed message ID -> fail closed;
- nonce replay -> rejected;
- provider selected `none`;
- `enabled=false`;
- `deployment_authorized=false`;
- `external_delivery_authorized=false`;
- send endpoint disabled.

## BigBird Mail acceptance

Service:

- unit: `bigbird-ai-gateway.service`;
- identity: `bigbird-ai:bigbird-ai`;
- listener: `127.0.0.1:8787`;
- accepted version: `0.3.5-alpha.1`;
- `/v1/health` passed after restart.

The BigBird deployment tree is not a separate Git checkout. Reviewed canonical Mail integration files from `integrations/bigbird_mail/` were deployed under BigBird's existing `app/integrations/` package. `main.py`, `tool_registry.py`, and the root-owned mode-0600 environment file were backed up before mutation; rollback remained available throughout acceptance.

Registered registry capabilities:

- `mail.status.read`;
- `mail.correspondence.read`;
- `mail.draft.prepare`.

All are marked `read_only=true`. `mail.draft.prepare` invokes only the preparation API and requires `prepared_not_sent`.

Acceptance passed:

- private-ai gateway authentication;
- Mail status `ready_local_native`;
- message read;
- thread read;
- prompt-like content remained untrusted;
- internal-viewer plus explicit Mail scopes accepted;
- registered-user Mail access denied;
- missing Mail scope denied;
- Mail draft -> `prepared_not_sent`;
- external delivery false.

## Final shared regression

UTC: `2026-08-19T03:48:20Z`.

Active units:

- `wwcx-messaging-gateway.service`;
- `wwcx-outbound-mail-gateway.service`;
- `bigbird-ai-gateway.service`;
- `wwcx-communications-workspace.service`;
- `edge1-comms-relay.service`;
- `asterisk.service`;
- `kamailio.service`.

Health/boundary observations:

- Messaging health -> pass;
- Mail health -> pass;
- BigBird health -> pass;
- telephony console health -> pass;
- telephony analytics health -> pass;
- Communications workspace has no accepted `/healthz` route at the probed path; service active on `127.0.0.1:8095`, root HTTP 404, POST HTTP 405;
- telephony analytics POST -> HTTP 405;
- expected private listeners present on 8095, 8096, 8099, 8104, 8787 and 58080;
- no new public BigBird/Mail/Messaging management listener;
- existing SIP 5060/5061 listeners observed only; no route/call mutation;
- no OOM-killer evidence in acceptance window;
- RAM about 3.8 GiB total / 1.9 GiB available at final check;
- root filesystem 64% used with about 28 GiB available;
- repository clean and synchronized to `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`.

Generic `systemctl --failed` also showed `bigbird-edge1-connector-maintenance.service` and `bigbird-edge1-connector.service` failed. These separate connector lifecycle units are not dependencies of the accepted UC runtime path above. They were not restarted or altered during this UC acceptance and should be tracked separately if connector health is desired.

## Final interpretation

`fresh_edge1_runtime_verified=true` is justified for the intended approved safe-scope Unified Communications requirements.

Runtime-ready/live-accepted:

- MMS private quarantine/scanner security;
- local-native Mail Room correspondence;
- dedicated Private AI Mail reads;
- prepared-not-sent Mail drafts;
- BigBird Mail registration;
- adjacent UC service regression.

Still intentionally separate/unproven:

- provider-native Mail (`production_provider_ready=false`);
- live mail/SMS/MMS routing/transmission;
- production call origination;
- fresh external carrier/interconnect health established by traffic;
- emergency routing/carrier mutation;
- quarantine release;
- provider credentials/contracts/DNS changes.
