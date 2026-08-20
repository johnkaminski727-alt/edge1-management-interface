# Edge1 Operator MCP commissioning closeout — 2026-08-20

## Scope

Non-secret commissioning evidence for the already accepted/persistent Secure MCP Tunnel and the focused production-clean Operator closeout. No secret values are recorded.

## Live authoritative verification

Verified through the live Edge1 Operator MCP:

- identity: `edge1.ww.cx`, principal `edge1-operator`, service ready;
- health: Operations API loopback-only, status OK, `mutations_enabled=false`;
- services: `edge1-secure-mcp-tunnel.service`, `edge1-operator-mcp.service`, and `bigbird-ai-tunnel.service` active;
- Big Bird health: OK, read-only mode;
- Apache: active/running;
- telephony: overall healthy; Asterisk service/process/listener evidence healthy;
- messaging: OK;
- time authority: healthy;
- disk: bounded filesystem probe succeeds;
- `edge1.network_state`: bounded runtime error remains on the deployed revision;
- snapshot network probes identify the exact cause as `Cannot open netlink socket: Address family not supported by protocol`;
- `edge1.asterisk_status`: native fixed CLI probes remain privilege-gated on the deployed revision; passive fallback succeeds.

Meaningful read-only audit event IDs from final verification:

- snapshot: `31d8011e-373c-4b1c-add3-7a010495d1c8`;
- Asterisk diagnostics: `b0f79426-15c6-421a-af76-ec79ffb95b57`;
- services: `8e2006c8-b9ff-48b4-91af-60b8797d800b`;
- Big Bird health: `cd3bd2ac-bda8-41e6-be81-e11f9e272a31`;
- repository status/head: `f4a51d94-58c9-4dfa-a631-8c65bfbf23a9`, `9b1a5105-02a2-41f5-a221-21628ed14528`;
- config digest: `c6de1a31-2f9c-4494-8762-b5e1a2c14016`;
- disk: `3924d724-18d8-4ac7-aa8c-a418d0b5cb55`;
- Apache: `4195ce1b-e978-4c07-85d4-1300bc341034`;
- telephony: `82fae6ae-994a-42b1-b6e4-110482cfa45e`;
- messaging: `87df4c13-82c4-418a-8962-8f4822d36a81`;
- time authority: `a5bbc7c0-9441-44b7-88ae-836ec5954193`.

## Revision reconciliation

Observed during closeout:

- remote `main` base at branch creation: `408bf253d308da1f310f82c9147c4184ec16d8cc`;
- live `/opt/edge1-management-interface`: clean `main` at `f3a20fb60783412758ab322a2f1a43defb2684c7`;
- MCP runtime `edge1.git_state`: detached `7496da7550ee46ef81142081b0a63fced7894e90`.

No live branch switch/reset was performed. The focused repository work is in PR #466 / branch `edge1/operator-mcp-commissioning-closeout-20260820`.

## Repository fixes prepared

- add only `AF_NETLINK` to the Operations API address-family sandbox;
- keep capability bounding/ambient sets empty and mutations disabled;
- lock the public MCP contract to exactly the intended 16 Edge1 tools;
- add standard read-only/non-destructive/closed-world/idempotent MCP annotations;
- exclude `agent.turn.status`, `agent.turn.handoff`, generic exec, and write surfaces;
- update the preserved-artifact classifier for the actual static/generated/unresolved set and reviewed compatibility symlink;
- add regression tests and update tunnel/completion runbooks.

## Asterisk control-socket evidence

Attended host-side inspection supplied during closeout established:

```text
/var/run/asterisk/asterisk.ctl
  type=socket
  owner=asterisk
  group=asterisk
  mode=0664

/run/asterisk
  owner=asterisk
  group=asterisk
  mode=0775

wwadmin groups:
  wwadmin, sudo, users, bigbird-audit
  not asterisk

wwadmin direct socket write/connect permission test:
  no
```

This proves the deployed Operations API principal does not currently have native Asterisk control-socket authority.

Adding `wwadmin` to group `asterisk` was deliberately rejected as the preferred repair. The Asterisk control socket is a general CLI control channel; group membership would allow the Operations API process itself to issue arbitrary Asterisk CLI commands if its local code path were broadened or compromised. That is wider authority than the public read-only MCP contract permits.

## Bounded Asterisk native diagnostic design

PR #466 now prepares an intermediary mechanism that does **not** grant Asterisk group membership, sudo authority, shell authority, a new network listener, or caller-controlled CLI strings to `wwadmin`.

Producer: `server/asterisk_readonly_snapshot.py`

- accepts no command-line parameters;
- contains exactly the seven reviewed read-only Asterisk CLI commands already used by Control Surfaces;
- runs under a dedicated systemd oneshot as `User=asterisk`, so socket access comes from the socket owner identity rather than delegated privilege;
- uses `Group=bigbird-audit` only for snapshot file sharing to the existing Operations API principal;
- runs with `NoNewPrivileges=true`, empty capability sets, and `RestrictAddressFamilies=AF_UNIX`;
- writes only `/run/edge1-asterisk-diagnostics/status.json` atomically;
- requires the runtime directory to be the exact non-symlink path created by systemd;
- writes mode `0640` and sanitizes command output before storage.

Consumer: `server/asterisk_operator_diagnostics.py`

- accepts no external target, command, host, port, or shell input;
- accepts the native snapshot only when it is a regular file owned by `asterisk:bigbird-audit`, mode `0640`;
- validates the exact snapshot contract and exact seven command IDs;
- requires every native check to have succeeded;
- rejects future-dated or older-than-90-second snapshots;
- otherwise falls back to the existing direct/passive Control Surfaces path, preserving passive fallback.

Systemd assets:

- `deploy/systemd/edge1-asterisk-readonly-snapshot.service`;
- `deploy/systemd/edge1-asterisk-readonly-snapshot.timer`.

The Operations API allowlist remains fixed/read-only and now routes only `asterisk.diagnostics` through the bounded snapshot consumer. `config.digest` covers both helper scripts and both systemd assets.

## Validation performed

Direct local execution during review:

- new Python producer/consumer compile checks: passed;
- fixed seven-command contract test: passed;
- fresh bounded snapshot acceptance: passed;
- stale snapshot rejection: passed;
- systemd unit syntax/verification: passed;
- public contract/sandbox reconstructed tests: passed;
- residual-classifier reconstructed behavior tests: passed.

Repository CI was also expanded so merge validation explicitly exercises:

- exact 16-tool public Edge1 Operator contract and standard annotations;
- residual security-boundary classifier regressions;
- `AF_NETLINK` presence with empty capability sets and no `CAP_NET_ADMIN`;
- exact bounded Asterisk allowlist routing;
- Asterisk producer/consumer safety tests;
- systemd unit verification.

Local/reconstructed checks are review evidence, not a substitute for repository CI or post-deployment host validation.

## Deployment/publication status

The closeout branch is **not deployed** by this record. Therefore:

- `edge1.network_state` remains expected to fail on the current live revision;
- `edge1.asterisk_status` remains expected to report native CLI limitation on the current live revision;
- repository annotations/contract hardening are not yet authoritative production evidence.

After reviewed merge and deliberate live revision reconciliation, deployment must back up the affected units/configuration, install the reviewed Operations API unit plus Asterisk snapshot service/timer, reload systemd, start/enable only the snapshot timer, restart only `edge1-operations-api.service`, and then verify through ChatGPT. Do not restart Big Bird or the Secure MCP Tunnel for this change.

Required post-deploy proofs include:

- `edge1.network_state` succeeds;
- `edge1.asterisk_status` reports useful native diagnostics with `native_cli_status=ok` and source `asterisk-owned-fixed-snapshot`;
- the snapshot file remains `asterisk:bigbird-audit 0640` and fresh;
- Operations API remains loopback-only with `mutations_enabled=false`;
- `wwadmin` remains outside group `asterisk`;
- exactly 16 Edge1 Operator tools remain exposed with truthful standard annotations;
- Big Bird and the Secure MCP Tunnel remain healthy.

Publication verdict at this stage: **NOT READY FOR WORKSPACE PUBLICATION**.

The tunnel itself remains accepted and persistent; publication remains blocked on reviewed merge/deployment and post-deploy live validation.

## Tunnel rollback

```sh
systemctl stop edge1-secure-mcp-tunnel.service
systemctl disable --now edge1-secure-mcp-tunnel.service
```

Do not alter the shared tunnel-client, Big Bird, firewall, DNS, SSH, Apache, certificates, SIP, SNMP, authentication, or unrelated production services as part of this rollback.
