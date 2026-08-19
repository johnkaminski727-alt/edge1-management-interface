# WW.CX Unified Communications — Live Closeout Handoff

Date: 2026-08-19
Repository: `johnkaminski727-alt/edge1-management-interface`
Live host: `edge1.ww.cx`
Accepted repository head: `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`
Evidence root: `/var/tmp/wwcx-uc-live-20260819T024027Z`

## Completion status

The approved safe-scope Unified Communications objective is complete and live-accepted.

`fresh_edge1_runtime_verified=true` for the intended UC safe-scope requirements.

No production communication authority was added.

## Accepted live capabilities

BigBird / WW.CX AI:

- `communications.read`;
- `telephony.read`;
- `messages.status.read`;
- `messages.conversation.read`;
- `messages.draft.prepare`;
- `mail.status.read`;
- `mail.correspondence.read`;
- `mail.draft.prepare`.

BigBird accepted runtime version: `0.3.5-alpha.1`, loopback `127.0.0.1:8787`.

Mail draft preparation is `prepared_not_sent`; retrieved Mail and Messaging content remains untrusted data.

## MMS final state

- private quarantine live at `/var/lib/wwcx-messaging-gateway/private-mms-quarantine`;
- directory permissions `0700`, files `0600`;
- `/usr/bin/clamscan` installed;
- signatures updated;
- clean -> `scanned_clean_held`;
- EICAR -> `quarantined_malicious`;
- restart recovery held;
- no clamd listener;
- no release authorization.

PR #444 fixed the intermediate-directory permission regression and merged as `28534e81396418b063006897248acba9c51af282`.

Routine warning: ClamAV 1.4.3 reported upstream 1.4.6 recommended; scanning/signature acceptance passed.

## Mail final state

- private root `/var/lib/wwcx-mail-room` mode `0700`;
- DB `correspondence.sqlite3` mode `0600`;
- two authoritative `local_native` RFC822 records accepted;
- explicit root/reply thread accepted;
- `wwcx-private-ai` dedicated HMAC client live;
- website-admin correspondence access remains denied;
- unsigned/replay/malformed-ID tests fail closed;
- Mail runtime reports `ready_local_native`;
- `production_provider_ready=false`;
- provider remains `none`;
- external delivery/send endpoint remain disabled.

PR #445 fixed missing runtime-application correspondence wiring and merged as `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`.

## BigBird Mail deployment state

Canonical reviewed Mail client/facade code lives in this repository under `integrations/bigbird_mail/`.

The running BigBird application tree at `/opt/bigbird-ai-gateway/app` is not a separate Git checkout. The reviewed Mail package was deployed into its existing `integrations` package; `main.py` and `tool_registry.py` were backed up and updated in place to register the three Mail capabilities. The existing protected HMAC secret was transferred into BigBird's root-owned mode-0600 environment file without display, disclosure, rotation or repository storage.

Rollback copies and acceptance evidence are retained under the evidence root.

## Shared regression state

Fresh 2026-08-19 regression confirmed active:

- Messaging Gateway;
- Outbound Mail Gateway;
- BigBird AI Gateway;
- Communications workspace;
- Communications Relay;
- Asterisk;
- Kamailio.

Private application listeners remained loopback-only. Communications workspace and telephony analytics continued rejecting POST with HTTP 405. No new public BigBird/Mail/Messaging listener and no OOM evidence were observed.

Existing SIP listeners were observed only; no call or route change was performed.

Two separate failed units were visible in the generic failed-unit listing:

- `bigbird-edge1-connector.service`;
- `bigbird-edge1-connector-maintenance.service`.

They are not dependencies of the accepted UC runtime path and were intentionally left untouched. Follow up separately if Edge1 connector lifecycle health is required.

## What is intentionally not complete

These are separate from the completed local safe scope:

- provider-native Mail source / `production_native` correspondence;
- production email transmission;
- production SMS/MMS transmission;
- production call origination;
- external carrier/interconnect health proven by traffic;
- emergency/carrier routing mutation;
- quarantine release;
- provider credential activation or rotation;
- DNS/firewall/certificate changes;
- number porting or STIR/SHAKEN;
- financial/legal/regulatory provider actions.

## Durable continuation points

Use:

- `.agent/unified-communications.md`;
- `.agent/unified-communications-backlog-20260818.md`;
- `config/communications/readiness-matrix-v1.json`;
- `config/communications/unified-communications.json`;
- `docs/communications/unified-communications-live-acceptance-20260819.md`;
- this handoff.

Do not reinterpret `runtime_ready` as permission for live production traffic. Production communication authority remains false.
