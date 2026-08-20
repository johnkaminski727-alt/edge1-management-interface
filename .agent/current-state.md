# Current State

Last reconciled: 2026-08-20  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`

This file is the concise cross-workstream continuation point. Historical details remain in dated acceptance/runbook records. Material Project Big Bird release/deployment chronology is maintained in the WW.CX website canonical Project Big Bird documentation, including `08 - Project Big Bird Release Deployment and Recovery Matrix.md` merged by PR #86.

## Repository / runtime reconciliation

Repository `main`, the shared engineering checkout, and the immutable production runtime are intentionally different architectural roles and must never be collapsed into one revision.

Current direct/repository evidence at this reconciliation:

```text
GitHub edge1-management-interface main = bf75563b13a08a0b9793be888fb3febfb9bdde52
shared /opt engineering checkout       = 234d00194cf7ef4abb6bdd466c7d9a6f1996fd99
immutable Operator/Operations runtime  = d326d4546abefa695a293266342a5c1075f010e2
```

The `bf75563...` repository head includes immediate removal of an accidental no-op `.agent/test-placeholder` file that had briefly been created with content `x`; both creation and rollback remain in Git history. It had no runtime or production effect. Do not hide or rewrite that audit trail.

## BigBird / Operations API

Fresh 2026-08-20 direct bounded state:

```text
BigBird AI version     = 0.3.5-alpha.1
BigBird health         = healthy
BigBird enabled        = true
BigBird mode           = read-only
Library integrity      = ok
Library                = 63 documents / 501 chunks
Operations API         = healthy
Operations actions     = 27
mutations_enabled      = false
```

The Edge1 BigBird AI `0.3.x` line is distinct from the historical shared-host Big Bird `v0.8.x`, V4.0.7 Observability R1, and G1 v0.2.0 namespaces.

## CHR-15 — BigBird connector lifecycle

Status: **SOURCE REPAIRED / LIVE ACCEPTANCE BLOCKED**.

PR #478 is merged as:

```text
28aa5c6c1ea24909f8a4765d4cc38c58fd46265a
```

The repair restores the connector state-write boundary and explicitly classifies all 27 Operations API actions while retaining the six enabled capabilities and fail-closed behavior.

Fresh live evidence still shows:

- `bigbird-edge1-connector.service` failed;
- `bigbird-edge1-connector-maintenance.service` failed;
- shared checkout `234d001...` predates PR #478.

The mounted Edge1 Operator is read-only and cannot perform the required source/config/unit backup, exact repair deployment and bounded refresh/restart acceptance. CHR-15 must remain open until a real authenticated live-write path proves the repair.

## Edge1 Operator / Secure MCP Tunnel

Status: **LIVE / ACCEPTED / PERSISTENT / WORKSPACE PUBLISHED**.

Accepted boundaries remain:

- Edge1 Operator MCP and Operations API use immutable detached runtime `d326d454...`;
- MCP loopback `127.0.0.1:8102`;
- Operations API loopback `127.0.0.1:8097`;
- exactly 16 public read-only Edge1 tools;
- no generic execution/write tool;
- turn-state persistence remains under `/var/lib/edge1-operator-mcp/turn-state` without weakening `ProtectSystem=strict`;
- BigBird tunnel and Edge1 Secure MCP Tunnel remain active at the bounded service level.

Asterisk native diagnostics work through the accepted Asterisk-owned fixed snapshot path. Do not widen access to the general Asterisk control socket.

## Public Edge1 front door

The 2026-08-19 front-door cutover remains **LIVE / ACCEPTED / REVERIFIED**. Existing route, PBX/SIP host, HTTPS and rollback boundaries remain unchanged. Rollback evidence remains:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh
```

HTTP 302 behavior is intentional; a 308 promotion is optional future work only.

## Global systemd trust boundary

Status: **LIVE / REPAIRED / VERIFIED**.

```text
/etc/systemd/system owner=root:root mode=0755
/var/lib/wwcx-deployment-evidence/systemd-unit-dir-boundary/20260820T011819Z
```

Future privileged changes under `/etc/systemd/system` remain separately gated.

## Control Surfaces / listener provenance

Fresh raw bounded listener classification still reports:

```text
internal-service=37
private-control=4
unknown-needs-attribution=22
```

`docs/control-surfaces/project-big-bird-evidence-reconciliation-20260820.md` reconciles those conservative labels against live interfaces and accepted service evidence. Eighteen of the 22 raw-unknown rows are now attributable without any exposure change:

- WireGuard-private DNS `10.77.0.1:53`;
- Chrony NTP UDP 123;
- WireGuard UDP 51820;
- Tailscale UDP 41641;
- Kamailio SIP TCP/UDP 5060 on private/public binds;
- NTS-KE TCP 4460;
- FreePBX UCP Node/PM2 TCP 8001/8003;
- Apache TCP 80/443.

Only four current rows remain genuinely unresolved by the mounted bounded evidence:

```text
UDP  0.0.0.0:57784
UDP  [::]:51550
TCP  100.115.195.54:40463
TCP  fd7a:115c:a1e0::5d39:c337:42639
```

The raw classifier may continue to say 22 until its static logic is deliberately changed. Do not change runtime classification merely to improve a count, and do not firewall/rebind/restart an unknown listener without a separate consumer/rollback review.

## Security-boundary residual evidence

The exact protected evidence directory is now durably identified:

```text
/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory/20260819T060856Z
```

Accepted aggregate remains:

```text
records=164
mapped=160
missing_known=0
unknown_preserved=4
filesystem_anomaly=1
security_inventory_rc=0
```

Retained hash anchors:

```text
result.json          f38f6e6d2fc099b1212fa26f00831f8e4abd0cdf76e366ab48f07227bc2dce18
sha256-manifest.txt  e7941f46073ef7c8da477ca949cb91f2377fb77c41b9cf8948da9fc02ded5f3a
```

The mounted Operator does not expose the protected reconciliation/anomaly metadata required to classify the remaining four preserved unknowns plus one filesystem anomaly. This is a bounded metadata-access blocker. Do not open secret contents or delete evidence to force completion.

## Control Surfaces / Asterisk evidence housekeeping

The corrected Asterisk warning-follow-up audit is durably retained:

```text
asterisk_warning_audit_rc=0
asterisk_warning_evidence=/var/lib/wwcx-deployment-evidence/asterisk-warning-followup/20260819T060845Z
```

The same 2026-08-19 transcript records the full executable Control Surfaces inventory as:

```text
control_surfaces_inventory_rc=126
```

Therefore that historical run is **not PASS**. The executable-mode/package defect was later repaired and current bounded diagnostics are operational, but no later retained full-script `rc=0` manifest was found in the available archive. A successful full-script manifest remains an evidence housekeeping task when an authenticated execution path is available.

## Business159 / CHR-18

Business159 Secure MCP Tunnel remains **OPERATIONALLY COMPLETE / PERSISTENT / ARCHIVE READY** and should not be reopened absent contrary evidence.

The latest retained accepted WW.CX website deployment checkpoint remains:

```text
source=01ee93cf0337006c5d44031a5f9eb1a83e1d0100
release=/home/wwcxjywl/releases/ww-cx-website/20260819T201010Z
backup=/home/wwcxjywl/shared/ww-cx-website/backups/public-html-20260819T201010Z.tar.gz
```

That retained checkpoint is not present-moment direct host proof. No current authenticated Business159 filesystem/shell connector is mounted, so CHR-18 remains open for verification of application checkout, document root, release/deployment state, PHP/HTTP behavior, and historical staging/private-core paths. Do not deploy merely to align documentation with GitHub `main`.

## Project Big Bird release/deployment documentation

CHR-16 and CHR-17 are completed on current evidence. The canonical WW.CX Project Big Bird matrix now separates:

- legacy/shared-host `v0.8.x`;
- V4.0.7 Observability R1;
- G1 v0.2.0;
- Edge1 BigBird AI `0.3.x`;
- Git source/runtime revisions;
- Business159 website release checkpoints.

`v0.8.0e3 Scheduled Brand Collections` is planned/staged but not proven deployed. Historical `v0.8.1` OCR/scanned-PDF work is planned/unresolved; no maintained implementation/deployment acceptance was found.

## Library/archive

Current private BigBird Library reports healthy at 1 collection / 63 documents / 501 chunks. The current canonical Project Big Bird primary sync set has ten unique hashes with no exact duplicates within that set. Import/re-index remains blocked until a reviewed bounded BigBird write/import path is available; the mounted Edge1 Operator is read-only.

Canonical Library/archive filing should continue in place without duplicate “final” packages. Provider/storage limitations must be recorded rather than represented as successful moves.

## DTMF provider work

Gmail was rechecked 2026-08-20. The newest VoIP.ms technical-thread response remains the 2026-08-14 notice that there was no update; no substantive later technical response was found.

```text
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

No provider matrix update, live calls, or DTMF transmission.

## Current continuation order

1. Complete CHR-15 live connector acceptance only when an authenticated backup/deploy/restart path is available.
2. Complete CHR-18 present-moment Business159 host verification only through an authenticated current host path.
3. Classify the four security unknowns and one filesystem anomaly only when bounded metadata/path/hash evidence is available.
4. Capture a successful full executable Control Surfaces manifest only through an approved execution path; never relabel the historical `rc=126` run.
5. Attribute the remaining four dynamic/Tailscale-local listener rows when exact process/consumer evidence becomes available.
6. Reconcile canonical Library copies/import as provider and target-write capability allow.
7. Leave DTMF provider work pending until a substantive reply arrives.

## Safety boundary

No credentials, secret values, private keys, tokens, cookies, tunnel secrets, protected customer data, or unnecessary sensitive personal information in Git/chat/evidence. No new public management listener. No DNS/firewall/certificate/authentication/SIP/carrier/emergency/alert/call/message/DTMF or destructive evidence action merely from this state file. For live changes: inspect -> expected state -> blast radius -> backup -> preflight -> smallest change -> validate -> verify -> record -> preserve rollback.
