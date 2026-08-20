# Edge1 Control Surfaces — Current State

Last reconciled: 2026-08-20  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Workstream: Control Surfaces / exposure reduction / permanent private operator

## Current disposition

The public front-door/exposure-reduction work remains accepted and unchanged. The private Edge1 Operator path is now fully commissioned, persistent, and published into the authorized ChatGPT workspace.

Fresh live diagnostics through the published bounded connector succeed for network state, Asterisk native diagnostics, Big Bird, services, Apache, inventory, and configuration status. The prior pre-publication assumptions that the tunnel was inactive and ChatGPT required human relay are obsolete.

## Public Edge1 behavior — accepted

Canonical ordinary public destination remains:

```text
https://ww.cx/time/
```

Accepted behavior includes raw/default HTTP root and exact `edge1.ww.cx` HTTPS root/index redirects to WW.CX Time, preserved `/edge1-status/`, preserved unknown/non-root behavior, unchanged raw HTTPS certificate/default-vhost handling, preserved PBX/SIP named-host behavior, and unchanged Apache/chronyd ownership expectations.

Protected rollback evidence:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
```

HTTP 302 remains intentional; 308 promotion is deferred and separate.

## FreePBX Administration / UCP boundary

Earlier accepted evidence records ordinary WAN FreePBX Administration/UCP denied while approved private management paths remain available. The front-door and Operator publication work did not broaden those rules.

Any future temporary/private native FreePBX session broker remains separately gated and must prove authentication/authorization, expiry, revocation, CSRF, audit, redirect/cookie/WebSocket compatibility, CSP/X-Frame-Options handling, listener/firewall equivalence, and rollback before activation.

## Published bounded Edge1 Operator

Accepted live state:

- `edge1-operator-mcp.service` active/enabled;
- `edge1-secure-mcp-tunnel.service` active/enabled;
- principal `edge1-operator`;
- MCP listener `127.0.0.1:8102` only;
- Operations API `127.0.0.1:8097` only;
- hardened service settings retained;
- bearer boundary retained;
- reviewed public contract is exactly 16 named parameterless read-only tools;
- Operations API reports 27 fixed actions and `mutations_enabled=false`;
- public dispatch excludes internal `agent.turn.*` capabilities;
- no generic `edge1.exec`, arbitrary command/path/URL/service/SQL/AMI/ARI action, or caller-selected Operations API mutation is exposed.

Production runtime remains pinned to immutable revision:

```text
d326d4546abefa695a293266342a5c1075f010e2
```

The primary engineering checkout may advance independently on `main`.

## Fresh diagnostic reconciliation

Current live bounded diagnostics show:

- network addresses/routes/listener classification succeed;
- Asterisk native diagnostics report `status=ok` and `native_cli_status=ok`;
- Asterisk source is the accepted `asterisk-owned-fixed-snapshot` path;
- snapshot contract remains no-parameter, `asterisk:bigbird-audit`, mode `0640`, fresh;
- Big Bird reports healthy, enabled and read-only with library integrity `ok`;
- Apache is active/running;
- telephony and adjacent core services remain active.

The earlier privilege-limited direct Asterisk CLI condition was solved without granting `wwadmin` Asterisk control-socket authority. Preserve that design: do not add `wwadmin` to group `asterisk`, add sudoers shell authority, or expose arbitrary Asterisk CLI merely to simplify diagnostics.

## General inventory and listener attribution

The historical `rc=126` inventory-script packaging defect was corrected by restoring Git mode `100755` on `scripts/control-surfaces-live-inventory.sh`.

Current bounded listener classification reports:

```text
internal-service=37
private-control=4
unknown-needs-attribution=22
```

Treat `unknown-needs-attribution` as provenance work, not automatic evidence of public exposure or a reason to change firewall/listener state. Historical exposure records already map several wildcard/direct-address services; reconcile those records before declaring a listener newly unexplained.

A final retained executable inventory manifest/summary remains useful housekeeping if a later evidence record has not already captured it.

## Secure MCP Tunnel

The Edge1 Secure MCP Tunnel is no longer staged-only. It is accepted, active, enabled, persistent, and successfully used by the published ChatGPT app.

The installed tunnel-client has a historical old-build raw-doctor compatibility quirk around missing OAuth protected-resource metadata. That finding was bounded during commissioning and is not an active failure of the accepted production path.

Do not add a public MCP proxy, fake OAuth authority, new WAN listener, firewall rule, authentication weakening, or shared tunnel-client replacement merely to change the historical doctor result.

## Asterisk warning follow-up

Accepted evidence confirms:

- configured PJSIP transport and Asterisk-owned loopback UDP `127.0.0.1:5061`;
- Asterisk active and boot-enabled through the systemd-sysv wrapper;
- loopback HTTP/HTTPS status interfaces;
- local TLS success;
- zero audit failures;
- current bounded fixed-snapshot native diagnostics succeed.

No listener, firewall, certificate, SIP, or startup-policy mutation is indicated. Retain the corrected warning-follow-up audit summary if it has not already been preserved in a later evidence record.

## Current execution path

Ordinary approved Edge1 operational questions should use the published bounded Edge1 Operator connector directly. Human paste-box relay remains appropriate only when a required action is outside the bounded connector surface or reaches a separately approval-gated production/security boundary.

Do not describe the bounded connector as a shell: it exposes fixed read-only tools only.

## Safety boundary

No credentials or secret values in chat/Git. No public MCP proxy. No new WAN management listener. No firewall/DNS/certificate/authentication change, carrier routing, emergency-path change, call/message origination, DTMF/alert transmission, or destructive action without its applicable explicit boundary and rollback evidence.
