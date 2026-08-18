# Unified Communications — Validation Record

Date: 2026-08-18
Scope: repository-side completion, CI evidence, and fresh authenticated Edge1 operator acceptance
Global fresh runtime completion: partial; persistent workspace is accepted, while its authoritative canonical event feed and MMS scanner/storage remain incomplete

## Accepted merged increments

| PR | Increment | Final head / merge evidence | CI result |
|---|---|---|---|
| #384 | Canonical event / identity / readiness / correlation core | merge `6b272fb0308bfeb161f50598845fc88b77e5c561` | Validate repository PASS; Edge1 Operator Validation PASS |
| #385 | SMS/MMS Private AI read + draft | merge `ce5c561304a0a7aa109b887d1739ae90660b7633` | Messaging Gateway PASS; BigBird Messaging Adapter PASS; Validate repository PASS; Edge1 Operator Validation PASS |
| #386 | Mail Room AI status + draft | merge `9e26ea6df6e0bc3469d3bc63701362b01a80bd94` | Validate repository PASS; Edge1 Operator Validation PASS |
| #387 | Unified Communications workspace | merge `2b4550812cb6bc790cb3b3bc0d079bdfd261b220` | Validate repository PASS; Edge1 Operator Validation PASS |
| #389 | MMS media quarantine foundation | merge `721d5e538835a4b53a05c2208e7940f1d83ec043` | Messaging Gateway PASS; Validate repository PASS; Edge1 Operator Validation PASS |
| #396 | Final repository reconciliation | merge `d7ccf2189a028df474ce5b7931870e10d6ec4292` | Validate repository PASS; Edge1 Operator Validation PASS |
| #397 | Fresh Edge1 UC acceptance reconciliation | merge `6d2c24dfb756bbb735dabc4ffca51d9a6a8b73fc` | Validate repository PASS; Edge1 Operator Validation PASS |
| #400 | Hardened Communications workspace service deployment | merge `a46ec4433033648c3428ce061318cdaf347a3605` | Validate repository PASS; Edge1 Operator Validation PASS |

## Contract validations

Repository validation now covers or is backed by focused tests for:

- canonical event validation and authoritative native-record provenance;
- rejection of embedded raw message/private/credential fields from the canonical layer;
- deterministic conversation ordering;
- metadata-only search allowlist;
- explicit-evidence identity links and rejection of name-similarity inference;
- retrieved/untrusted metadata inability to grant scopes or tool authority;
- quarantine release fail-closed behavior;
- SMS/MMS read-token enforcement and sanitized media projection;
- SMS/MMS draft != send;
- Mail draft != send and no network activity;
- provider/source failure-safe boundaries;
- loopback-only workspace binding and rejection of mutation verbs;
- hardened persistent workspace service deployment and rollback;
- JavaScript syntax and responsive workspace assets;
- MMS pending-scan, missing-digest, malicious, scan-error, and clean-held states;
- SMS quarantine not-applicable semantics where no media exists.

## Evidence interpretation

`Edge1 Operator Validation` is a repository CI workflow name. Green CI remains CI evidence only. Fresh live claims below come from operator-run SSH acceptance against `edge1.ww.cx` and are kept separate from repository evidence.

The global `fresh_edge1_runtime_verified` flag remains false until the intended safe-scope runtime surfaces are complete. Fresh acceptance of Messaging Gateway, BigBird, Mail AI, and the persistent Communications workspace does not imply production-traffic authorization and does not hide the still-missing authoritative workspace feed or MMS trusted scanner/private storage.

## Fresh Edge1 acceptance — 2026-08-18

### Messaging Gateway

PASS:

- `wwcx-messaging-gateway.service` live as version `0.4.2`;
- health and readiness PASS on loopback `127.0.0.1:58080`;
- authenticated `messages.status.read` and `messages.conversation.read` PASS;
- recent conversation contract `wwcx.messages-conversation-read.v1` PASS;
- untrusted-content marker and `mutation_authorized: false` PASS;
- fail-closed MMS quarantine projection PASS with `release_authorized: false`;
- bounded restart performed only after in-memory event count was confirmed zero;
- rollback retained at `/opt/wwcx-messaging-gateway-staging/app.pre-uc-20260818T075057Z` with evidence rollback script under `/tmp/edge1-uc-evidence-20260818T073658Z/`;
- no SMS/MMS traffic generated.

Known limitation: storage remains `memory`.

### BigBird messaging adapter

PASS:

- live adapter source matched the validated candidate for `client.py` and `tools.py`;
- authenticated conversation reads against Messaging Gateway `0.4.2` PASS;
- local `prepare_reply` PASS with `prepared_not_sent`, `send_authorized: false`, and `mutation_authorized: false`;
- control-disabled check PASS;
- rollback retained at `/var/backups/bigbird-ai-gateway-uc-messaging-20260818T080100Z`.

### BigBird registry and signed chat boundary

PASS:

- live BigBird version `0.3.4-alpha.3`;
- mode remains `read-only`;
- tool count increased from six to eight while preserving the original six tools;
- `messages.conversation.read` registered read-only;
- `messages.draft.prepare` registered read-only as local artifact preparation only;
- explicit scope authorization PASS;
- missing-scope rejection PASS;
- live conversation read PASS;
- live draft preparation PASS;
- messaging control remained disabled;
- unsigned `/v1/chat` returned HTTP `401`;
- adjacent UC services remained active;
- rollback retained at `/var/backups/bigbird-ai-gateway-uc-chat-20260818T081344Z`;
- no authorized model/chat request, SMS/MMS, email, or call was generated.

### Mail AI adapter

PASS for local bounded adapter behavior:

- `mail.status.read`;
- `mail.draft.prepare`;
- prepared-not-sent semantics;
- no send/mutation authority.

Still blocked: `mail.correspondence.read` pending an explicitly authorized authoritative native Mail Room correspondence source.

### Communications workspace — persistent Phase 10 acceptance

PASS:

- exact merged source gate confirmed live repo HEAD and `origin/main` at `a46ec4433033648c3428ce061318cdaf347a3605` before deployment;
- detached candidate syntax/readiness validation PASS;
- ephemeral detached-runtime health PASS before installation;
- persistent `wwcx-communications-workspace.service` installed, enabled, active, and running;
- detached runtime installed at `/opt/wwcx-communications-workspace` without changing the live `/opt/edge1-management-interface` worktree;
- service identity `wwadmin:wwadmin` confirmed;
- listener is `127.0.0.1:8095` only; wildcard listener rejection PASS;
- `/communications/healthz` HTTP 200 and read-only status PASS;
- `/communications/api/v1/readiness` HTTP 200 PASS;
- `/communications/api/v1/events?limit=1` HTTP 200 with honest zero-event state because no canonical snapshot/feed is attached;
- returned event payload preserved `content_is_untrusted: true` and `mutation_authorized: false`;
- POST to events returned HTTP 405 with `read_only_workspace` and `mutation_authorized: false`;
- `/communications/` static workspace returned HTTP 200;
- repository status before/after deployment compared identical;
- adjacent Messaging, Mail, BigBird, Relay, Asterisk, Kamailio, telephony analytics, and telephony console services remained active;
- no recent kernel OOM evidence was observed during the preflight;
- manual rollback retained at `/tmp/edge1-uc-evidence-20260818T073658Z/rollback-communications-workspace-20260818T082857Z.sh`;
- no reverse proxy/public listener, SMS/MMS, email, call, route, or credential change occurred.

Intentionally incomplete:

- no authoritative canonical communications-event snapshot/feed is attached, therefore `event_count=0` is the truthful operational state;
- global `fresh_edge1_runtime_verified` remains false.

Operational warning:

- `free -h` showed about 1.5 GiB available memory and the workspace used about 11.4 MiB, but the configured 1 GiB swap allocation was fully consumed by the end of Phase 10;
- no recent kernel OOM evidence was found;
- the operator shell did not expose the `swapon` command, so `free -h` is the retained swap-usage evidence from this pass;
- avoid unnecessary broad service restarts until memory/swap pressure is separately investigated.

### MMS scanner/private quarantine runtime

NOT COMPLETE:

- `clamscan`, `clamdscan`, and `freshclam` not installed;
- ClamAV service/socket inactive;
- no existing quarantine-storage candidate found in the inspected `/var/lib`, `/srv`, or `/opt` paths;
- no package installation performed.

The fail-closed metadata foundation is live, but security remains deliberately degraded until trusted scanning and private storage are attached. Quarantine release remains unauthorized.

## Remaining fresh acceptance work

1. Identify and attach an authoritative canonical metadata feed/snapshot source for the persistent workspace without substituting audit logs or fabricated data.
2. Approved private MMS quarantine storage and trusted scanner integration with fail-closed degradation testing.
3. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized.
4. Fresh functional Voice/SIP and Communications Relay acceptance if required for the final global runtime flag.
5. Final readiness/handoff reconciliation after the remaining safe-scope items are complete or explicitly blocked.

Do not use production calls, messages, or email as acceptance tests. Production SMS/MMS, mail send, call origination, routing, quarantine release, credentials, DNS/firewall/certificate/authentication changes, porting, STIR/SHAKEN, financial or contractual actions remain separately controlled.
