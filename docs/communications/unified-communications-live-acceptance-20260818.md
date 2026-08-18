# WW.CX Unified Communications — Fresh Edge1 Runtime Acceptance

Date: 2026-08-18
Host: `edge1.ww.cx`
Repository baseline: `a46ec4433033648c3428ce061318cdaf347a3605`
Evidence path used during operator acceptance: `/tmp/edge1-uc-evidence-20260818T073658Z`

## Scope and evidence model

This record captures fresh operator-run SSH acceptance evidence for the safe, non-traffic Unified Communications scope. It does not convert runtime readiness into permission for production SMS/MMS, email transmission, call origination, routing changes, quarantine release, credential changes, or other separately controlled actions.

The live runtime and repository remain separate evidence sources. `/opt/bigbird-ai-gateway` is a deployed runtime rather than a Git worktree, and the Communications workspace is deployed from a detached runtime copy, so runtime state below is recorded explicitly instead of being inferred from repository state.

## Messaging Gateway

Fresh live acceptance completed for `wwcx-messaging-gateway.service` on loopback port `58080`.

Accepted state:

- service version `0.4.2`;
- service active after bounded restart;
- `/healthz` returned `status: ok`;
- `/readyz` returned `status: ready`, storage `memory`;
- authenticated status read returned capabilities `messages.status.read` and `messages.conversation.read`;
- authenticated recent-conversation read returned contract `wwcx.messages-conversation-read.v1`;
- returned conversation content is explicitly untrusted;
- read responses preserve `mutation_authorized: false`;
- event count was zero during the restart state-loss gate;
- MMS quarantine projection reported `foundation_ready_fail_closed`, default `quarantined_pending_scan`, and `release_authorized: false`;
- no SMS/MMS traffic was generated.

Deployed source hashes recorded during acceptance:

- `main.py`: `a9c255ca258ed8c60b92a8de78da879d9899604d79b37caa2e71944e256992f1`
- `media_quarantine.py`: `15139eaba5f1f941e89311fb957beeb63a843d315acb2483d00a86e724cba359`
- `persistence.py`: `76f80dead8172728a500d64de8cab998c99077c758f22c5e939c979cba17d751`
- `store.py`: `da82fe4758f65fbf1981561dc5e30a4fe6d2c2fdeb7938e870980be47b184ad3`

Rollback points retained:

- original runtime directory: `/opt/wwcx-messaging-gateway-staging/app.pre-uc-20260818T075057Z`
- rollback script: `/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-20260818T075057Z.sh`

The gateway still uses memory storage. Durable message storage remains a separate operational consideration.

## BigBird Private AI messaging adapter

The runtime adapter under `/opt/bigbird-ai-gateway/app/integrations/bigbird_messaging` was upgraded and accepted before registry expansion.

Accepted adapter behavior:

- exact candidate parity was verified for `client.py` and `tools.py`;
- authenticated conversation reads succeeded against Messaging Gateway `0.4.2`;
- local reply preparation returned `drafted` / `prepared_not_sent`;
- prepared drafts preserved `send_authorized: false` and `mutation_authorized: false`;
- messaging control remained disabled;
- BigBird remained active and read-only after restart;
- adjacent UC services remained active.

Protected rollback backup:

`/var/backups/bigbird-ai-gateway-uc-messaging-20260818T080100Z`

## BigBird registry and signed chat path

Fresh activation then expanded the private signed chat authorization surface from six to eight read-only tools.

Accepted BigBird runtime:

- version `0.3.4-alpha.3`;
- mode `read-only`;
- listener remained loopback-only on `127.0.0.1:8787`;
- tool count `8`;
- library integrity remained `ok` with 63 indexed documents, 501 chunks, and zero rejected documents;
- an unsigned `/v1/chat` request returned HTTP `401`, preserving the signed request boundary.

Accepted registry tools:

- `communications.read`
- `edge1.status.read`
- `library.document.read`
- `library.search`
- `messaging.status.read`
- `messages.conversation.read`
- `messages.draft.prepare`
- `telephony.read`

For the new messaging capabilities:

- `messages.conversation.read` requires its explicit scope and fails closed when absent;
- `messages.draft.prepare` requires its explicit scope and remains local preparation only;
- missing-scope validation failed closed as expected;
- conversation data remained untrusted;
- messaging control remained disabled;
- no authorized `/v1/chat` request was generated during acceptance, so no external model request was needed for the runtime test;
- no SMS/MMS was sent.

Protected rollback backup:

`/var/backups/bigbird-ai-gateway-uc-chat-20260818T081344Z`

## Mail AI adapter

Fresh local acceptance confirmed the Mail AI adapter contract with:

- `mail.status.read`;
- `mail.draft.prepare`;
- prepared-not-sent semantics;
- no send/mutation authority;
- `mail.correspondence.read` still blocked pending an explicitly authorized authoritative native Mail Room correspondence source.

No email was sent for acceptance.

## Communications workspace

The workspace first passed ephemeral acceptance and then persistent Phase 10 activation from exact repository commit `a46ec4433033648c3428ce061318cdaf347a3605`.

Persistent accepted state:

- `wwcx-communications-workspace.service` is installed, enabled, active, and running;
- detached runtime is `/opt/wwcx-communications-workspace`;
- service identity is `wwadmin:wwadmin`;
- listener is `127.0.0.1:8095` only;
- wildcard listener rejection passed;
- `/communications/healthz` returned HTTP 200 with read-only status;
- `/communications/api/v1/readiness` returned HTTP 200;
- `/communications/api/v1/events?limit=1` returned HTTP 200 with zero events because no canonical snapshot/feed is attached;
- the empty event response remains explicitly untrusted and `mutation_authorized: false`;
- POST to the events API returned HTTP 405 with `read_only_workspace`;
- `/communications/` returned HTTP 200;
- the live `/opt/edge1-management-interface` worktree was byte-for-byte unchanged according to before/after Git status evidence;
- all adjacent UC services remained active after activation;
- no reverse proxy or public listener was added;
- no production communications traffic or credential change occurred.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-communications-workspace-20260818T082857Z.sh`

The workspace is now persistently runtime-ready, but it is intentionally empty. No authoritative canonical runtime event snapshot/feed has yet been selected or attached, so global `fresh_edge1_runtime_verified` remains false.

Resource note from Phase 10: about 1.5 GiB memory remained available and no recent kernel OOM evidence was found, but the configured 1 GiB swap allocation was fully consumed. The workspace itself used about 11.4 MiB. This warning is retained separately from the successful workspace functional acceptance.

## MMS scanner and quarantine runtime

Fresh inspection found no installed `clamscan`, `clamdscan`, or `freshclam`, no active ClamAV service/socket, and no existing quarantine-storage candidate directory under the inspected `/var/lib`, `/srv`, or `/opt` paths.

Accordingly:

- the fail-closed MMS quarantine metadata foundation is live in the Messaging Gateway;
- trusted malware scanning is not yet attached;
- private quarantine storage is not yet attached;
- quarantine release remains unauthorized;
- MMS security readiness remains degraded rather than overstated.

No package installation was performed during this pass.

## Adjacent UC services

Fresh service checks after the accepted Messaging Gateway, BigBird, and Communications workspace changes showed these services active:

- `wwcx-messaging-gateway.service`
- `wwcx-outbound-mail-gateway.service`
- `bigbird-ai-gateway.service`
- `edge1-comms-relay.service`
- `asterisk.service`
- `kamailio.service`
- `wwcx-telephony-analytics.service`
- `wwcx-telephony-console.service`
- `wwcx-communications-workspace.service`

Service-active evidence alone is not used to claim new functional acceptance for unrelated capabilities.

## Remaining safe-scope work

The remaining safe work is now narrow:

1. identify and attach an authoritative canonical metadata feed/snapshot source for the persistent workspace without substituting unrelated audit logs or fabricated data;
2. attach approved private MMS quarantine storage and a trusted scanner, preserving fail-closed behavior and keeping release separately authorized;
3. resolve `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized;
4. complete fresh functional Voice/SIP and Communications Relay acceptance if required for the final global runtime flag;
5. reconcile the final readiness/handoff state once the remaining safe items are complete or explicitly blocked.

Production/provider activation remains outside this acceptance. Do not infer authorization for carrier traffic, live mail send, call origination, SIP/carrier/emergency-route changes, number porting, STIR/SHAKEN, quarantine release, DNS/firewall/certificate/authentication changes, credentials, financial actions, or other separately controlled operations.
