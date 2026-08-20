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
- `edge1.asterisk_status`: native fixed CLI probes remain privilege-gated; passive fallback succeeds.

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

- remote `main` base: `408bf253d308da1f310f82c9147c4184ec16d8cc`;
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

Direct reconstructed-source validation performed during review:

- public contract/sandbox tests: 3 passed;
- residual-classifier behavior tests: 5 passed;
- Python compile checks for reconstructed changed Python logic: passed.

These local checks are review evidence, not a substitute for repository CI or post-deployment host validation.

## Asterisk limitation

The available MCP tools do not expose the ownership/mode of `/var/run/asterisk/asterisk.ctl`. Without that evidence, no group, sudoers, socket-permission, or helper change was made. This preserves least privilege. The minimum acceptable native mechanism remains a narrowly scoped read-only mechanism selected only after live socket metadata is inspected; passive fallback remains mandatory.

## Deployment/publication status

The closeout branch is **not deployed** by this record. Therefore `edge1.network_state` remains expected to fail on the current live revision and the repository annotations/contract hardening are not yet authoritative production evidence.

Publication verdict at this stage: **NOT READY FOR WORKSPACE PUBLICATION**.

The tunnel itself remains accepted and persistent; publication is blocked only on reviewed merge/deployment, post-deploy live validation, and resolution or explicit acceptance of the bounded Asterisk native-diagnostics limitation.

## Tunnel rollback

```sh
systemctl stop edge1-secure-mcp-tunnel.service
systemctl disable --now edge1-secure-mcp-tunnel.service
```

Do not alter the shared tunnel-client, Big Bird, firewall, DNS, SSH, Apache, certificates, SIP, SNMP, authentication, or unrelated production services as part of this rollback.
