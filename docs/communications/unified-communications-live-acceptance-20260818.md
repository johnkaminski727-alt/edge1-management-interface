# WW.CX Unified Communications — Fresh Edge1 Runtime Acceptance

Date: 2026-08-18
Host: `edge1.ww.cx`
Repository baseline: `d7ccf2189a028df474ce5b7931870e10d6ec4292`
Evidence path used during operator acceptance: `/tmp/edge1-uc-evidence-20260818T073658Z`

## Scope and evidence model

This record captures fresh operator-run SSH acceptance evidence for the safe, non-traffic Unified Communications scope. It does not convert runtime readiness into permission for production SMS/MMS, email transmission, call origination, routing changes, quarantine release, credential changes, or other separately controlled actions.

The live runtime and repository remain separate evidence sources. `/opt/bigbird-ai-gateway` is a deployed runtime rather than a Git worktree, so the runtime state below is recorded explicitly instead of being inferred from repository state.

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

The loopback-only Unified Communications workspace was accepted ephemerally on port `8095`:

- health returned read-only status;
- readiness returned repository-ready state without fabricating live acceptance;
- empty/no-snapshot state returned zero events honestly;
- POST returned HTTP `405` with the read-only boundary preserved;
- the temporary listener was removed successfully after the test.

A later fresh inspection confirmed:

- `wwcx-communications-workspace.service` is not installed;
- port `8095` is free;
- no authoritative canonical runtime snapshot source has yet been attached.

Therefore the workspace is repository-ready and ephemerally accepted, but not yet persistently deployed.

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

Fresh service checks after the accepted Messaging Gateway and BigBird changes showed these services active:

- `wwcx-messaging-gateway.service`
- `wwcx-outbound-mail-gateway.service`
- `bigbird-ai-gateway.service`
- `edge1-comms-relay.service`
- `asterisk.service`
- `kamailio.service`
- `wwcx-telephony-analytics.service`
- `wwcx-telephony-console.service`

Service-active evidence alone is not used to claim new functional acceptance for unrelated capabilities.

## Remaining safe-scope work

The remaining safe work is now narrow:

1. install and accept a persistent loopback-only Communications workspace service and attach an authoritative canonical metadata snapshot source;
2. attach approved private MMS quarantine storage and a trusted scanner, preserving fail-closed behavior and keeping release separately authorized;
3. resolve `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized;
4. reconcile this fresh runtime evidence into project readiness records and final handoff.

Production/provider activation remains outside this acceptance. Do not infer authorization for carrier traffic, live mail send, call origination, SIP/carrier/emergency-route changes, number porting, STIR/SHAKEN, quarantine release, DNS/firewall/certificate/authentication changes, credentials, financial actions, or other separately controlled operations.
