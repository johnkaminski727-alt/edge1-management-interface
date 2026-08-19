# Current State

Last reconciled: 2026-08-19  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`

This file is the concise cross-workstream continuation point. Historical details remain in dated acceptance/runbook records.

## Repository / public front door

The 2026-08-19 Edge1 public front-door cutover is LIVE / ACCEPTED and must not be reopened without fresh contrary evidence.

Accepted ordinary routing remains:

- raw/default IPv4 HTTP `/` -> `302 https://ww.cx/time/`;
- unmatched Host HTTP `/` -> same;
- `edge1.ww.cx` HTTP `/` -> existing `301 https://edge1.ww.cx/`;
- `edge1.ww.cx` HTTPS `/` and `/index.html` -> `302 https://ww.cx/time/`;
- `/edge1-status/` preserved;
- unknown/non-root paths preserved;
- raw HTTPS behavior not weakened;
- PBX/SIP named-host behavior preserved;
- Apache and chronyd listener ownership preserved.

Rollback evidence remains:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh
```

HTTP 302 is intentional. Any 308 promotion is future optional work.

## Edge1 Operator / Secure MCP Tunnel

The bounded server-side Operator is already accepted live:

- `edge1-operator-mcp.service` active/enabled;
- principal `edge1-operator`;
- MCP loopback `127.0.0.1:8102` only;
- Operations API loopback `127.0.0.1:8097` only;
- bearer boundary retained; unauthenticated MCP returns 401;
- reviewed contract is 16 named parameterless read-only tools;
- Operations API mutations remain disabled.

Secure MCP Tunnel staging and local credential provisioning have advanced:

- `/etc/edge1-tunnel/tunnel-id` exists as `root:edge1-operator` mode `0640` and is readable by `edge1-operator` without exposing its value;
- `/etc/edge1-tunnel/runtime-api-key` exists with the same restricted ownership/mode/readability;
- `/etc/edge1-operator/mcp-token` remains `edge1-operator:edge1-operator` mode `0600`;
- installed tunnel-client remains `0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144`, SHA-256 `937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100`;
- `edge1-secure-mcp-tunnel.service` is still disabled/inactive;
- `bigbird-ai-tunnel.service` remains active/enabled;
- no tunnel start/enable command has been run.

### Doctor result

Raw doctor returned exit code 2 with exactly one failed check:

```text
FAILED_CHECKS oauth_metadata
HTTP 404 from http://127.0.0.1:8102/.well-known/oauth-protected-resource/mcp
```

This is a reviewed compatibility issue in the installed tunnel-client build, not a reason to add fake OAuth endpoints. Exact installed upstream source unconditionally requires OAuth metadata for every HTTP target, while later upstream source treats all-404 OAuth metadata discovery as optional for plain/non-OAuth MCP servers. Edge1 intentionally uses its existing loopback bearer boundary and supplies that Authorization header through both tunnel runtime and discovery static-header configuration.

Do not replace the shared tunnel-client solely to clear this result while the accepted Big Bird tunnel uses it.

Compatibility record:

`docs/edge1-operator/15-tunnel-doctor-compatibility-20260819.md`

Next read-only gate:

```text
deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh
```

Only after that fail-closed compatibility gate passes may attended tunnel activation be considered. Starting `edge1-secure-mcp-tunnel.service` remains an explicit production/account-linked boundary. Persistence stays blocked until attended tunnel + ChatGPT acceptance succeeds.

No direct `edge1.*` MCP connector is attached to this ChatGPT session yet.

## Security-boundary inventory

The current read-only security-boundary inventory has run successfully on Edge1. Aggregate result:

```text
records=164
mapped=160
missing_known=0
unknown_preserved=4
filesystem_anomaly=1
```

Apache config testing passed. The inventory reported no live configuration/source-tree/traffic-control mutation and did not collect credentials/cookie values.

Remaining work is narrow: record the exact timestamped evidence directory and classify the four preserved unknowns plus one filesystem anomaly using path/mode/hash/relationship metadata only before any restricted-release/public-tree work proceeds.

DNS, firewall, certificates, authentication policy, listeners, and production traffic remain separately gated.

## Asterisk / alerting

The read-only warning follow-up is complete at the service/configuration level:

- Asterisk active;
- PJSIP transport configuration exists;
- Asterisk owns loopback UDP `127.0.0.1:5061`;
- SysV `S01asterisk` startup links exist in runlevels 2-5 and `systemctl is-enabled` reports enabled through the systemd-sysv wrapper;
- TCP `8089` is loopback-only;
- local TLS 1.3 handshake succeeds using the Edge1 certificate;
- audit produced zero failures.

No listener/firewall/certificate/SIP/startup-policy mutation is justified. The repository audit script still needs a small output-handling fix so systemd-sysv informational stderr cannot create a false warning.

The offline CAP-CP/EBS laboratory remains isolated; no `Actual` alert delivery, calls/pages, tones, or public delivery path are authorized by this state.

## Control Surfaces

Fresh bounded diagnostics for summary/listeners/Asterisk/Kamailio/FreePBX completed. Native CLI diagnostics may be privilege-limited while passive fallback evidence succeeds and higher-level telephony health remains healthy. Do not widen permissions merely to make a diagnostic card green.

The general inventory script failure is understood: `scripts/control-surfaces-live-inventory.sh` is mode `0644`, so direct execution returns 126 while `bash scripts/control-surfaces-live-inventory.sh` succeeds. Repository mode should be corrected to executable and the inventory rerun; this is not a host `noexec` condition.

Existing FreePBX Admin/UCP private-source boundaries remain unchanged. Any temporary/private native-session mechanism remains separately gated.

## DTMF provider work

Externally blocked. Mailbox recheck on 2026-08-19 found no substantive provider technical answer after the 2026-08-14 notice that there was still no update.

Keep:

```text
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

No live calls or DTMF transmission without separate explicit authorization.

## Current continuation order

1. Keep the accepted public front door unchanged.
2. Merge/validate the repository compatibility and executable-mode corrections.
3. Run the fail-closed Secure MCP Tunnel compatibility validator read-only.
4. Classify the five remaining security-inventory records metadata-only and capture the exact evidence directory.
5. Rerun the executable Control Surfaces inventory and reconcile results.
6. Stop at the attended tunnel-activation boundary for explicit approval.
7. Leave DTMF provider work pending until an external response arrives.

## Safety boundary

No credentials or secret values in Git/chat/evidence. No public MCP proxy. No new WAN management listener. Do not modify DNS, firewall, certificates, authentication, production traffic, SIP/carrier routing, emergency behavior, alert delivery, calls/DTMF, or retained evidence merely from this state file. Inspect first; preserve unrelated work; back up before mutations; validate; preserve rollback; stop at explicit credential/account/security/production boundaries.
