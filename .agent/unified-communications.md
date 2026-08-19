# Unified Communications — Current State

Last reconciled: 2026-08-19, fresh Edge1 safe-scope live acceptance complete
Repository: `johnkaminski727-alt/edge1-management-interface`
Live host: `edge1.ww.cx`
Authenticated operator principal: `wwadmin`
Repository head accepted live: `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`
Evidence root: `/var/tmp/wwcx-uc-live-20260819T024027Z`
Global `fresh_edge1_runtime_verified`: **true** for the approved Unified Communications safe scope

## Current truth

WW.CX Communications remains non-sending/non-originating by default. The approved safe-scope Unified Communications objective is now functionally complete and live-accepted on Edge1 without enabling production communication traffic.

Accepted live local chain:

`local RFC822 -> private Mail Room SQLite store -> authenticated loopback Mail API -> BigBird Private AI -> mail.correspondence.read / mail.draft.prepare`

Accepted live MMS security chain:

`private content-addressed MMS quarantine -> fixed /usr/bin/clamscan -> held clean/malicious/failure states -> no automatic release`

Production-native/provider Mail remains separately unproven and is not required for this local safe-scope completion. Production mail/SMS/MMS/call traffic remains unauthorized.

## Repository and deployment changes

Phase 28 implementation PR #427 merged as `e7d7fda638a4f69d68bf54cdebdbee9070143384`.

Safe-scope approval PR #443 merged as `86ecece2f474dafc0a0e4b64a4fafba3185d4cef`.

During live acceptance two defects were found and durably corrected:

- PR #444, `Keep MMS quarantine directories private`, fixed intermediate quarantine parents that Python could otherwise create as mode `0755`; exact live correction and fresh-tree regression passed. Merge: `28534e81396418b063006897248acba9c51af282`.
- PR #445, `Wire Mail correspondence reads into runtime gateway`, connected correspondence status/message/thread methods through the actual `RuntimeGatewayApplication` entry point. Merge: `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`.

The Edge1 repository was clean and exactly synchronized to `b5537e2baf551cb36f3ecab902e9b47eef5a5e95` at final shared regression.

## MMS live acceptance

Live Messaging service: `wwcx-messaging-gateway.service`, identity `wwadmin:wwadmin`, loopback `127.0.0.1:58080`.

Completed:

- installed command-line ClamAV and signature updater without `clamav-daemon`;
- live scanner version observed: ClamAV `1.4.3`; fresh signatures loaded, daily DB version `28096`;
- no TCP ClamAV daemon listener on port 3310;
- created `/var/lib/wwcx-messaging-gateway/private-mms-quarantine` outside web roots;
- all quarantine directories verified mode `0700`; files mode `0600`;
- deployed reviewed quarantine implementation hash matching repository;
- clean fixture -> `scanned_clean_held`;
- EICAR fixture -> `quarantined_malicious`;
- restart/re-open persistence -> held;
- `release_authorized=false` throughout;
- Messaging service restart and `/healthz` passed.

The upstream ClamAV package reported that 1.4.3 is older than recommended 1.4.6. Signature update succeeded and scanning acceptance passed; this is a maintenance warning, not an acceptance failure.

## Mail Room live acceptance

Live Mail service: `wwcx-outbound-mail-gateway.service`, identity `wwcx-mail-gateway:wwcx-mail-gateway`, loopback `127.0.0.1:8104`.

Private store:

- `/var/lib/wwcx-mail-room` owner `wwcx-mail-gateway`, mode `0700`;
- `correspondence.sqlite3` owner `wwcx-mail-gateway`, mode `0600`;
- two local RFC822 fixtures ingested as authoritative `local_native` records;
- root/reply explicit threading passed;
- content remained `content_is_untrusted=true`;
- send and mutation authorization remained false.

Authentication/runtime:

- existing HMAC secret mechanism reused without disclosure or rotation;
- exact dedicated client `wwcx-private-ai` added alongside `wwcx-website-admin`;
- correspondence reads enabled only against `/var/lib/wwcx-mail-room/correspondence.sqlite3`;
- unsigned correspondence request -> HTTP 401;
- `wwcx-website-admin` correspondence request -> HTTP 401;
- `wwcx-private-ai` status/message/thread reads -> accepted;
- status -> `ready_local_native`;
- `production_provider_ready=false` and `source_truth=local_native_only`;
- malformed message ID failed closed;
- nonce replay rejected;
- provider selection remained `none`;
- gateway `enabled=false`, `deployment_authorized=false`, `external_delivery_authorized=false`, send endpoint disabled.

## BigBird Private AI live acceptance

Live service: `bigbird-ai-gateway.service`, identity `bigbird-ai:bigbird-ai`, loopback `127.0.0.1:8787`.

The running BigBird tree is a deployment artifact rather than a separate Git repository. Canonical Mail client/facade code remains in this repository under `integrations/bigbird_mail/`; those reviewed files were deployed into the BigBird integration package. Live BigBird API wiring was backed up and changed in place with rollback retained in the protected evidence directory.

Accepted live BigBird version: `0.3.5-alpha.1`.

Registered capabilities:

- `mail.status.read`;
- `mail.correspondence.read`;
- `mail.draft.prepare`.

All three are registry-classified read-only; draft preparation remains `prepared_not_sent` and cannot authorize delivery.

Acceptance passed:

- dedicated `wwcx-private-ai` gateway authentication;
- local-native Mail status;
- individual message read;
- two-message thread read;
- prompt-like correspondence remained untrusted data;
- internal-viewer + explicit Mail scopes accepted;
- registered-user Mail access denied;
- missing Mail scope denied;
- Mail draft `prepared_not_sent`;
- external delivery remained false;
- BigBird restart and `/v1/health` passed;
- Mail and BigBird listeners remained loopback-only.

## Final shared regression

Fresh final regression at `2026-08-19T03:48:20Z` verified active:

- `wwcx-messaging-gateway.service`;
- `wwcx-outbound-mail-gateway.service`;
- `bigbird-ai-gateway.service`;
- `wwcx-communications-workspace.service`;
- `edge1-comms-relay.service`;
- `asterisk.service`;
- `kamailio.service`.

Messaging, Mail, BigBird, telephony console, and telephony analytics health probes passed. The Communications workspace has no `/healthz` route at the probed path; its service remained active on loopback `127.0.0.1:8095`, root returned HTTP 404, and POST returned HTTP 405, preserving the read-only boundary. Telephony analytics POST also returned HTTP 405.

No new public BigBird/Mail/Messaging management listener was observed. Existing SIP listeners were observed only and were not changed. No OOM-killer evidence appeared in the acceptance window. Root filesystem remained 64% used with about 28 GiB available.

`bigbird-edge1-connector-maintenance.service` and `bigbird-edge1-connector.service` were present in failed state during the final generic failed-unit listing. They are separate Edge1 connector lifecycle units, not dependencies of the accepted UC runtime paths above. No attempt was made to restart or repair them as part of this UC completion; track separately if desired.

## Readiness interpretation

- approved safe-scope UC live deployment: **complete**;
- fresh Edge1 safe-scope runtime verification: **true**;
- MMS private quarantine/security scanning: **security-ready and live-accepted**;
- local-native Mail correspondence: **runtime-ready and live-accepted**;
- BigBird Mail status/correspondence/draft integration: **runtime-ready and live-accepted**;
- provider-native Mail: **unproven/optional separate work**;
- Voice/SIP external carrier/interconnect health: **not freshly established by traffic; no call was originated**;
- production communication traffic authority: **blocked/unchanged**;
- quarantine release: **blocked/unchanged**.

## Protected boundaries

No safe-scope completion grants live SMS/MMS or email transmission, production calls, emergency/carrier routing changes, number porting, STIR/SHAKEN signing, credential disclosure/rotation, quarantine release, destructive/irreversible operations, provider financial/legal/regulatory commitments, or unrelated DNS/firewall/certificate/public-listener changes.

Detailed live evidence record: `docs/communications/unified-communications-live-acceptance-20260819.md`.
Final handoff: `docs/handoff/unified-communications-live-closeout-20260819.md`.
