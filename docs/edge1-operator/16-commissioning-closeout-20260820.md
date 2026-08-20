# Edge1 Operator MCP commissioning closeout — 2026-08-20

## Scope

Non-secret commissioning evidence for the already accepted/persistent Secure MCP Tunnel and the focused production-clean Operator closeout. No secret values are recorded.

## Live authoritative verification

Verified through the live Edge1 Operator MCP before deployment of this closeout:

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

Meaningful read-only audit event IDs:

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
- lock the public MCP discovery contract to exactly the intended 16 Edge1 tools;
- enforce the same 16-tool allowlist at `tools/call`, so hand-crafted calls cannot reach internal `agent.turn.*` adapter capabilities;
- add standard read-only/non-destructive/closed-world/idempotent MCP annotations;
- exclude generic exec and write surfaces from the public app;
- update the preserved-artifact classifier for the actual static/generated/unresolved set and reviewed compatibility symlink;
- add regression tests, CI gates, a bounded deployment helper, and updated tunnel/completion documentation.

The adapter may retain `agent.turn.status` and `agent.turn.handoff` for explicitly internal workflows. The public Edge1 Operator entrypoint rejects those names as `unknown_tool` before adapter invocation. This preserves internal protocol evolution without expanding the app contract.

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

Adding `wwadmin` to group `asterisk` was deliberately rejected. The control socket is a general Asterisk CLI channel, so direct group access would grant broader authority than the public read-only MCP contract requires.

## Bounded Asterisk native diagnostic design

PR #466 prepares an intermediary mechanism that does **not** grant Asterisk group membership, sudo authority, shell authority, a new network listener, or caller-controlled CLI strings to `wwadmin`.

Producer: `server/asterisk_readonly_snapshot.py`

- accepts no caller parameters;
- contains exactly the seven reviewed read-only Asterisk CLI commands already used by Control Surfaces;
- runs as `User=asterisk` under a hardened systemd oneshot;
- uses `Group=bigbird-audit` only for snapshot sharing to the existing Operations API principal;
- uses `NoNewPrivileges=true`, empty capability sets, and `RestrictAddressFamilies=AF_UNIX`;
- writes only `/run/edge1-asterisk-diagnostics/status.json` atomically;
- rejects symlink path indirection;
- writes sanitized mode-`0640` output.

Consumer: `server/asterisk_operator_diagnostics.py`

- accepts no target, command, host, port, or shell input;
- accepts only a regular `asterisk:bigbird-audit 0640` snapshot;
- validates the exact contract, exact seven command IDs, success state, and freshness;
- rejects future-dated or older-than-90-second snapshots;
- otherwise preserves the existing direct/passive fallback.

Systemd assets:

- `deploy/systemd/edge1-asterisk-readonly-snapshot.service`;
- `deploy/systemd/edge1-asterisk-readonly-snapshot.timer`.

The Operations API allowlist remains fixed/read-only and routes only `asterisk.diagnostics` through the bounded snapshot consumer. `config.digest` covers the Asterisk helper assets and the public MCP protocol/entrypoint boundary.

## Security-boundary classifier

The fail-closed residual classifier now understands the actual preserved set:

- `network-sensor/data/network-sensor.json` — generated JSON; validate safe file/JSON structure, not stale historical size/hash;
- `network-sensor/index.html` — repository-static; require exact match to `src/web/network-sensor/index.html`;
- `operations-center/snmp.html` — explicitly preserved unresolved artifact; do not overwrite to manufacture Git provenance;
- `snmp/operations-snmp.json` — generated JSON; validate safe file/JSON structure, not stale historical size/hash;
- `security-correlation.json` — reviewed compatibility symlink with exact contained-target validation.

Unexpected paths, malformed generated JSON, unsafe file types/modes, static-source mismatch, or symlink drift fail closed.

## Validation performed

Direct review validation passed for the new Asterisk producer/consumer, fixed seven-command contract, fresh/stale snapshot behavior, systemd unit verification, public contract/sandbox logic, and residual classifier behavior.

Repository CI was expanded to exercise:

- exact 16-tool public discovery contract and standard annotations;
- direct-call rejection of `agent.turn.*` through the public app entrypoint;
- `AF_NETLINK` with empty capability sets and no `CAP_NET_ADMIN`;
- exact bounded Asterisk allowlist routing and helper safety tests;
- residual security-boundary classifier regressions;
- deployment-helper shell syntax.

CI and local checks are merge evidence, not substitutes for post-deployment host validation.

## Bounded deployment helper

`deploy/edge1-operator/install-commissioning-closeout.sh` is the reviewed deployment path after merge and deliberate live Git reconciliation.

It:

- requires `edge1.ww.cx`, clean `main`, and an exact reviewed revision argument for `--apply`;
- requires the observed Asterisk socket boundary and refuses if `wwadmin` gains `asterisk` group membership;
- validates the Operations API sandbox, helper units, public protocol, local loopback health, and local unauthenticated MCP HTTP `401` before mutation;
- records protected evidence and backups under `/var/lib/wwcx-deployment-evidence/edge1-operator-commissioning-closeout/`;
- installs only the reviewed Operations API unit and Asterisk snapshot service/timer;
- starts/enables only the new snapshot timer;
- restarts only the directly affected `edge1-operations-api.service` and `edge1-operator-mcp.service`;
- does not restart `edge1-secure-mcp-tunnel.service` or Big Bird;
- verifies loopback-only listeners, disabled Operations API mutations, fresh bounded Asterisk native diagnostics, tunnel persistence, and Big Bird tunnel health;
- automatically invokes its recorded unit rollback if a post-mutation validation fails.

Repository revision rollback remains separate: create a safety branch before any live fast-forward and do not use force push/history rewriting.

## Deployment/publication status

The closeout branch is **not deployed** by this record. Therefore the current live revision is still expected to show the known network runtime error and limited native Asterisk CLI diagnostics.

Required post-deploy proofs include:

- `edge1.identity` and `edge1.health` remain clean;
- `edge1.network_state` succeeds;
- `edge1.asterisk_status` reports useful native diagnostics with `native_cli_status=ok` and source `asterisk-owned-fixed-snapshot`;
- the snapshot remains `asterisk:bigbird-audit 0640` and fresh;
- Operations API remains loopback-only with `mutations_enabled=false`;
- local MCP remains loopback-only and bearer-protected;
- `wwadmin` remains outside group `asterisk`;
- exactly 16 Edge1 Operator tools remain exposed with truthful standard annotations;
- direct calls to internal `agent.turn.*` remain rejected by the public app;
- Big Bird and the Secure MCP Tunnel remain healthy;
- final protected evidence records the exact tested revision and meaningful audit IDs without secret values.

Publication verdict at this stage: **NOT READY FOR WORKSPACE PUBLICATION**.

The tunnel itself remains accepted and persistent; publication remains blocked on reviewed merge/deployment and post-deploy live validation.

## Tunnel rollback

```sh
systemctl stop edge1-secure-mcp-tunnel.service
systemctl disable --now edge1-secure-mcp-tunnel.service
```

Do not alter the shared tunnel-client, Big Bird, firewall, DNS, SSH, Apache, certificates, SIP, SNMP, authentication, or unrelated production services as part of this rollback.
