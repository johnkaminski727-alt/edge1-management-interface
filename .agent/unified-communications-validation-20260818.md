# Unified Communications — Validation Record

Date: 2026-08-18
Scope: repository-side completion, CI evidence, and fresh authenticated Edge1 operator acceptance
Global fresh runtime completion: partial; persistent workspace and MMS scanner/storage remain incomplete

## Accepted merged increments

| PR | Increment | Final head / merge evidence | CI result |
|---|---|---|---|
| #384 | Canonical event / identity / readiness / correlation core | merge `6b272fb0308bfeb161f50598845fc88b77e5c561` | Validate repository PASS; Edge1 Operator Validation PASS |
| #385 | SMS/MMS Private AI read + draft | merge `ce5c561304a0a7aa109b887d1739ae90660b7633` | Messaging Gateway PASS; BigBird Messaging Adapter PASS; Validate repository PASS; Edge1 Operator Validation PASS |
| #386 | Mail Room AI status + draft | merge `9e26ea6df6e0bc3469d3bc63701362b01a80bd94` | Validate repository PASS; Edge1 Operator Validation PASS |
| #387 | Unified Communications workspace | merge `2b4550812cb6bc790cb3b3bc0d079bdfd261b220` | Validate repository PASS; Edge1 Operator Validation PASS |
| #389 | MMS media quarantine foundation | merge `721d5e538835a4b53a05c2208e7940f1d83ec043` | Messaging Gateway PASS; Validate repository PASS; Edge1 Operator Validation PASS |

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
- JavaScript syntax and responsive workspace assets;
- MMS pending-scan, missing-digest, malicious, scan-error, and clean-held states;
- SMS quarantine not-applicable semantics where no media exists.

## Evidence interpretation

`Edge1 Operator Validation` is a repository CI workflow name. Green CI remains CI evidence only. Fresh live claims below come from operator-run SSH acceptance against `edge1.ww.cx` and are kept separate from repository evidence.

The global `fresh_edge1_runtime_verified` flag remains false until the intended safe-scope runtime surfaces are complete. Fresh acceptance of Messaging Gateway, BigBird, and the Mail AI adapter does not imply production-traffic authorization and does not hide the still-missing persistent Communications workspace or MMS trusted scanner/private storage.

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

### Communications workspace

Ephemeral acceptance PASS:

- loopback-only server accepted on port `8095`;
- health/readiness PASS;
- empty/no-snapshot event state represented honestly;
- POST rejected with HTTP `405`;
- temporary listener removed successfully.

Persistent deployment NOT COMPLETE:

- `wwcx-communications-workspace.service` not installed;
- port `8095` free after ephemeral acceptance;
- authoritative canonical runtime snapshot source not attached.

### MMS scanner/private quarantine runtime

NOT COMPLETE:

- `clamscan`, `clamdscan`, and `freshclam` not installed;
- ClamAV service/socket inactive;
- no existing quarantine-storage candidate found in the inspected `/var/lib`, `/srv`, or `/opt` paths;
- no package installation performed.

The fail-closed metadata foundation is live, but security remains deliberately degraded until trusted scanning and private storage are attached. Quarantine release remains unauthorized.

## Remaining fresh acceptance work

1. Persistent loopback-only Communications workspace service deployment and health acceptance.
2. Authoritative canonical metadata snapshot source attachment for the workspace.
3. Approved private MMS quarantine storage and trusted scanner integration with fail-closed degradation testing.
4. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized.
5. Final readiness/handoff reconciliation after the above safe-scope items are complete or explicitly blocked.

Do not use production calls, messages, or email as acceptance tests. Production SMS/MMS, mail send, call origination, routing, quarantine release, credentials, DNS/firewall/certificate/authentication changes, porting, STIR/SHAKEN, financial or contractual actions remain separately controlled.
