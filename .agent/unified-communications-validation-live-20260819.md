# Unified Communications — Live Validation Record

Date: 2026-08-19
Host: `edge1.ww.cx`
Operator: `wwadmin`
Repository head accepted: `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`
Evidence root: `/var/tmp/wwcx-uc-live-20260819T024027Z`

## Result

Approved safe-scope Unified Communications live validation: **PASS**.

`fresh_edge1_runtime_verified=true` for the intended UC safe scope.

## Repository/CI corrections incorporated

- PR #444 head `9527f65692102887d0557ad20ebe816af9d5f05b` fixed MMS intermediate quarantine permissions; CI passed; merge `28534e81396418b063006897248acba9c51af282`.
- PR #445 head `2a5bca36494eaa7b51759d371d83fe5b17420e34` wired correspondence methods into the actual Mail runtime application; repository, runtime-path, disabled-migration, and Edge1 operator validations passed; merge `b5537e2baf551cb36f3ecab902e9b47eef5a5e95`.

## MMS validation

PASS:

- ClamAV command-line scanner present;
- signatures updated successfully;
- no clamd/3310 listener;
- private quarantine root outside web tree;
- all quarantine directories `0700`;
- all quarantine files `0600`;
- fresh-tree permission regression;
- clean -> `scanned_clean_held`;
- EICAR -> `quarantined_malicious`;
- restart recovery -> held;
- `release_authorized=false`;
- Messaging service active and `/healthz` passed.

Maintenance warning only: installed ClamAV 1.4.3 reported upstream 1.4.6 recommended.

## Mail validation

PASS:

- `/var/lib/wwcx-mail-room` `0700`;
- DB `0600`;
- two local RFC822 records persisted;
- source `local-mailroom-rfc822`;
- scope `local_native`;
- authoritative true;
- explicit root/reply threading;
- untrusted/no-send/no-mutation projections;
- dedicated HMAC client `wwcx-private-ai`;
- unsigned correspondence denied;
- website-admin correspondence denied;
- private-ai status/message/thread accepted;
- `ready_local_native`;
- `production_provider_ready=false`;
- malformed ID fails closed;
- nonce replay rejected;
- provider `none`;
- external delivery false;
- send endpoint disabled;
- Mail service active and loopback-only.

## BigBird validation

PASS:

- version `0.3.5-alpha.1`;
- service active on `127.0.0.1:8787`;
- reviewed `bigbird_mail` package deployed;
- `mail.status.read` registered read-only;
- `mail.correspondence.read` registered read-only;
- `mail.draft.prepare` registered read-only/prepared-not-sent;
- gateway authentication accepted as `wwcx-private-ai`;
- message/thread reads accepted;
- prompt-like Mail content remains untrusted;
- internal-viewer + required scopes accepted;
- registered-user denied;
- missing Mail scope denied;
- draft -> `prepared_not_sent`;
- external delivery false;
- restart and `/v1/health` passed.

## Shared regression

At `2026-08-19T03:48:20Z`:

PASS active state:

- `wwcx-messaging-gateway.service`;
- `wwcx-outbound-mail-gateway.service`;
- `bigbird-ai-gateway.service`;
- `wwcx-communications-workspace.service`;
- `edge1-comms-relay.service`;
- `asterisk.service`;
- `kamailio.service`.

PASS HTTP/boundary observations:

- Messaging health;
- Mail health;
- BigBird health;
- telephony console health;
- telephony analytics health;
- Communications workspace active on loopback, root HTTP 404, POST HTTP 405;
- telephony analytics POST HTTP 405;
- no new public BigBird/Mail/Messaging management listener;
- no ClamAV daemon listener;
- MMS/Mail private permissions preserved;
- no OOM-killer evidence;
- repository clean and synchronized.

Observed, not UC-blocking:

- `bigbird-edge1-connector-maintenance.service` failed;
- `bigbird-edge1-connector.service` failed.

Those connector lifecycle units are outside the accepted UC service path and were not changed.

## Boundaries retained

No live SMS/MMS/email traffic, call origination, carrier/emergency routing mutation, quarantine release, credential disclosure/rotation, provider activation, DNS/firewall/certificate change, destructive operation or commercial/legal/regulatory action was performed or authorized by this acceptance.
