# Telephony Analytics Live Acceptance — 2026-08-01

## Decision

The read-only Edge1 Telephony Analytics service is **accepted** for its current loopback-only aggregate-observability scope.

This acceptance does not authorize carrier routing, PBX configuration, call origination, DTMF transmission, number assignment, emergency-calling changes, database access, credential access, production collector activation, write-plane operations, or public exposure.

## Authenticated execution

- host: `edge1.ww.cx`;
- principal: `wwadmin`;
- authoritative repository: `/opt/edge1-management-interface`;
- branch: `main`;
- accepted repository head: `cb7c5174fa17e9c145ec549e8a8b7d29ac3cc628`;
- audit timestamp: `2026-08-01T19:16:42Z`;
- audit exit code: `0`;
- warnings: `0`;
- failures: `0`.

## Protected evidence

Analytics evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/20260801T191636Z
```

Analytics evidence-manifest SHA-256:

```text
31a21acfe7888bfcab971af6de8b7aa4c23ff22fe31ae56fdc99ad9a54e1b336
```

Repository-metadata evidence:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T191636Z
```

Repository-metadata evidence-manifest SHA-256:

```text
ba5c949567b7dd8655dd7dbe76d75bc69dcb96f988cf46517148bd9b9abfc4cf
```

Live payloads remain only in the protected evidence directory and are not committed to the repository.

## Service and boundary verification

The audit confirmed:

- `wwcx-telephony-analytics.service` was active and enabled;
- the service ran as `wwadmin:wwadmin`;
- systemd hardening included `PrivateTmp=yes`, `ProtectHome=yes`, `ProtectSystem=strict`, `NoNewPrivileges=yes`, and `MemoryDenyWriteExecute=yes`;
- the analytics listener was restricted to `127.0.0.1:8099`;
- no wildcard listener was present on port `8099`;
- the API remained read-only;
- POST to the health endpoint returned HTTP `405`;
- aggregate endpoint payload validation passed;
- the privacy scan passed;
- no customer identifiers were retained by the acceptance evidence.

Validated endpoints:

- `/healthz`;
- `/api/telephony/platform/health`;
- `/api/telephony/platform/calls/summary`;
- `/api/telephony/platform/interconnects/summary`.

## Runtime source provenance

The installed service executes from the existing worktree:

```text
/opt/wwcx-worktrees/telephony-analytics-pr63/server/telephony_analytics_api.py
```

The associated platform module is:

```text
/opt/wwcx-worktrees/telephony-analytics-pr63/server/telephony_platform.py
```

The runtime files matched the canonical `main` checkout byte-for-byte:

- analytics API SHA-256: `269861d79ef310e94e58764b241ab5190f3087d31135686364c07526678db980`;
- telephony platform SHA-256: `39f108c5c275b4b0966c5b0d8350d1e3e75c82a9283e05024df79448feb25fbd`;
- `runtime_api_source_match=yes`;
- `runtime_platform_source_match=yes`.

The alternate worktree path is therefore accepted for the measured runtime revision. This acceptance does not imply that future changes in either checkout remain equivalent without another source-provenance check.

## Repository ownership verification

The repository index remained securely owned and writable by the repository owner:

- path: `/opt/edge1-management-interface/.git/index`;
- owner: `wwadmin:wwadmin`;
- mode: `0600`;
- index ownership preserved during the root-run audit: `yes`;
- repository state after the audit: clean.

The audit executes Git inspection as the repository owner and fails if index ownership changes.

## Non-actions

The accepted audit performed no:

- service installation, start, stop, restart, reload, enablement, or configuration change;
- runtime mutation;
- call origination;
- DTMF transmission;
- database query;
- credential read;
- carrier or route change;
- firewall, DNS, certificate, or public-listener change.

## Remaining boundaries

Still outside this acceptance:

- sanitized CDR and SIP-event collectors connected to production data sources;
- database-backed or credential-bearing collectors;
- carrier integrations and carrier-performance conclusions;
- dashboard write actions or operational automation;
- anomaly enforcement or fraud blocking;
- routing, trunk, dial-plan, extension, registration, or number-management changes;
- production calls, messages, DTMF, emergency-path tests, and external exposure.
