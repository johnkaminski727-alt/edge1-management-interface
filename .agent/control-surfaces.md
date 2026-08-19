# Edge1 Control Surfaces — Current State

Last reconciled: 2026-08-19  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Workstream: Control Surfaces / exposure reduction / permanent private operator

## Current disposition

The public front-door/exposure-reduction work is accepted and unchanged. The bounded Edge1 Operator is live on loopback. Fresh read-only diagnostics show the native-card degradation is a privilege-boundary presentation issue with successful passive fallback, not evidence that Asterisk, Kamailio, or FreePBX is down.

## Public Edge1 behavior — accepted

Canonical ordinary public destination remains:

```text
https://ww.cx/time/
```

Accepted behavior includes raw/default HTTP root and exact `edge1.ww.cx` HTTPS root/index redirects to WW.CX Time, preserved `/edge1-status/`, preserved unknown/non-root behavior, unchanged raw HTTPS certificate/default-vhost handling, preserved PBX/SIP named-host behavior, and unchanged Apache/chronyd listener ownership.

Protected rollback evidence:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
```

HTTP 302 remains intentional; 308 promotion is deferred and separate.

## FreePBX Administration / UCP boundary

Earlier accepted evidence records ordinary WAN FreePBX Administration/UCP denied while approved private management paths remain available. The 2026-08-19 front-door change did not broaden those rules.

Any future temporary/private native FreePBX session broker remains separately gated and must prove authentication/authorization, expiry, revocation, CSRF, audit, redirect/cookie/WebSocket compatibility, CSP/X-Frame-Options handling, listener/firewall equivalence, and rollback before activation.

## Bounded Edge1 Operator

Current accepted server-side state:

- `edge1-operator-mcp.service` active/enabled;
- principal `edge1-operator`;
- MCP listener `127.0.0.1:8102` only;
- Operations API `127.0.0.1:8097` only;
- hardened service settings retained;
- bearer boundary retained; unauthenticated MCP returns 401;
- reviewed contract is 16 named parameterless read-only tools;
- Operations API loopback true and mutations disabled.

No generic `edge1.exec`, arbitrary command/path/URL/service/SQL/AMI/ARI action, or caller-selected Operations API mutation is exposed.

## Fresh diagnostic reconciliation

The approved read-only run exercised bounded `summary`, `listeners`, `asterisk`, `kamailio`, and `freepbx` diagnostics.

Result:

- bounded diagnostic execution completed;
- native CLI actions may report limited/unavailable under the restricted Operator principal;
- passive fallback evidence succeeds;
- higher-level telephony health remains healthy;
- no evidence supports widening service-account permissions or weakening hardening merely to make a diagnostic card green.

Treat this as an accepted privilege-boundary presentation condition unless future evidence shows functional service loss.

## General inventory script

The previous `rc=126` from `scripts/control-surfaces-live-inventory.sh` is explained: the repository file was mode `0644`, so direct execution was denied; interpreter execution succeeded and the repository filesystem is not `noexec`.

PR #450 corrects the Git mode to `100755`. Its dedicated Control Surfaces inventory workflow passes. After merge, fast-forward the clean Edge1 checkout and rerun the script directly as a read-only inventory; no production service change is required merely for this packaging correction.

## Secure MCP Tunnel

Local tunnel ID/runtime-key provisioning is complete with restricted metadata, but `edge1-secure-mcp-tunnel.service` remains disabled/inactive. The installed shared tunnel-client raw doctor returns one reviewed old-build false negative on missing OAuth protected-resource metadata. Edge1 does not rely on DCR/PRMD; it uses its existing bearer boundary and tunnel static Authorization headers.

PR #450 adds:

```text
deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh
```

The gate is fail-closed: it pins the exact reviewed tunnel-client version/SHA before doctor, verifies the loopback target/header contract, and accepts the old result only when `oauth_metadata` is the sole failure and local bearer/404 behavior remains exact. An unreviewed replacement tunnel-client fails before doctor even if it would otherwise report success.

See `docs/edge1-operator/15-tunnel-doctor-compatibility-20260819.md`.

Do not add a public MCP proxy, fake OAuth authority, new WAN listener, firewall rule, authentication weakening, or shared tunnel-client replacement as a workaround.

## Asterisk warning follow-up

Fresh read-only evidence confirms:

- configured PJSIP transport and Asterisk-owned loopback UDP `127.0.0.1:5061`;
- Asterisk active and boot-enabled through the systemd-sysv wrapper with `S01asterisk` links in runlevels 2-5;
- TCP `8089` loopback-only;
- local TLS 1.3 handshake succeeds;
- zero audit failures.

No listener, firewall, certificate, SIP, or startup-policy mutation is indicated. PR #450 corrects the audit's enablement capture so systemd-sysv informational stderr no longer creates a false warning; static safety validation passes. Rerun the corrected read-only audit after the Edge1 checkout fast-forwards.

## Current execution path

Until the private ChatGPT tunnel is attached, authenticated live work remains a human-relay path: ChatGPT prepares bounded commands, the authenticated operator runs them on Edge1, and sanitized output/evidence is returned for validation. Do not describe this as direct autonomous shell execution.

## Safety boundary

No credentials or secret values in chat/Git. No public MCP proxy. No new WAN management listener. No firewall/DNS/certificate/authentication change, carrier routing, emergency-path change, call/message origination, DTMF/alert transmission, or destructive action without its applicable explicit boundary and rollback evidence.
