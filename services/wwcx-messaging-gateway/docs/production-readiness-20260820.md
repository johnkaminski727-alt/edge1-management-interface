# WW.CX Messaging production-readiness matrix

Date: 2026-08-20

This matrix deliberately separates implementation, test evidence, deployment, configuration, authorization, reachability and live acceptance. A true value in one column must never be interpreted as authority for another.

| Capability | Implemented | Tested | Deployed private | Provider configured | Credentials configured | Publicly reachable | Authorized | Live accepted | Evidence / blocker |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| PostgreSQL message persistence | yes | yes | yes | n/a | n/a | no | yes private | yes private | Phase 3 live acceptance; migrations 0001-0008 |
| Durable inbound webhook receipts / replay | yes | yes | yes | simulator only | simulator only | no | yes private | yes private | verified receipt/recovery/collision acceptance |
| STOP / START / HELP suppression | yes | yes | yes | provider-neutral | n/a | no | yes private | yes private | ordering and manual-suppression preservation tested |
| Durable outbound queue | yes | yes | yes | simulator only | no real carrier | no | no real traffic | yes synthetic | worker remains disabled persistently |
| Outbound authorization / rate policy | yes | yes | yes | provider-neutral | n/a | no | no real traffic | yes synthetic | persistent runtime policy remains disabled |
| DLR reconciliation | yes | yes | yes | simulator only | no real carrier | no | yes private | yes synthetic | duplicate/stale ordering acceptance complete |
| Uncertain-send fail-closed handling | yes | yes | yes | provider-neutral | n/a | no | yes private | yes synthetic | ambiguous outcomes require reconciliation |
| Private MMS quarantine storage | yes | yes | source/live evidence required for latest tree | provider-neutral | n/a | no | quarantine only | private acceptance required | content-addressed digest-verified store; clean remains held |
| Trusted malware-scanner adapter | yes | yes with controlled doubles | runtime scanner status must be freshly verified | provider-neutral | scanner-specific | no | scan only | not claimed | scanner availability must be proven at runtime |
| Telnyx webhook/send adapter | yes | yes in CI | no | no | no | no | no | no | adapter source exists but is deliberately unregistered |
| Real carrier number / DID | no | n/a | no | no | no | no | no | no | purchase/assignment is explicit approval boundary |
| Public carrier webhook | source route exists | provider mock tested | no | no | no | no | no | no | requires TLS/reverse-proxy/firewall/DNS/security review and approval |
| BigBird messaging status read | yes | yes | yes | n/a | private read token | no | read only | yes private | live BigBird tool registry confirms capability |
| BigBird conversation read | yes | yes | yes | n/a | private read token | no | read only | yes private | content explicitly untrusted; mutation false |
| BigBird prepared-not-sent draft | yes | yes | yes | n/a | private read scope | no | draft only | yes private | send_authorized false |
| AI-authorized send | intentionally absent | boundary tested | absent | n/a | n/a | no | no | no | AI output can never authorize delivery |
| Unified Communications workspace | yes | yes | yes | n/a | n/a | private/controlled | read only | live service healthy | browser visual acceptance for current Messaging redesign still required |
| Messaging Operations legacy console | yes basic | yes historical | published state requires fresh verification | n/a | n/a | controlled path | sandbox only | historical | substantial modernization still required |
| Monitoring / health / readiness | yes | yes | yes | n/a | n/a | private | read only | yes private | gateway health/readiness and operator probes healthy |
| Alert delivery | design pending destination | no | no | n/a | n/a | no | no | no | private notification destination not selected |
| Backup / rollback | yes | yes historically | yes | n/a | n/a | no | yes | yes private | `/var/backups/wwcx-messaging-gateway/phase3-final-20260819T010540Z` |

## Fresh ground truth captured for this mission

- GitHub `main` before the carrier increment: `e27caead6a5cb3664bee770d95af92bf6583b835`.
- PR #483 merged the unregistered Telnyx adapter as `27bff5d58b03876b21ea45888343751ed4b40f91` after Messaging Gateway, repository, and Edge1 Operator CI all passed.
- The shared `/opt/edge1-management-interface` engineering checkout was observed clean but behind GitHub main at `234d00194cf7ef4abb6bdd466c7d9a6f1996fd99`.
- The immutable Edge1 Operator runtime was observed clean at detached `d326d4546abefa695a293266342a5c1075f010e2`; repository operations records identify that pin as intentional, not unexplained drift.
- `wwcx-messaging-gateway.service`, PostgreSQL, BigBird, Communications workspace, Apache, Asterisk and Kamailio were observed active.
- Messaging health returned `status=ok`; the listener remained loopback-only at `127.0.0.1:58080`.
- `bigbird-edge1-connector.service` and `bigbird-edge1-connector-maintenance.service` were observed failed. They remain unresolved runtime-health defects until authenticated Edge1 execution is available to inspect logs/unit intent and repair, supersede or retire them.

## Operational conclusion

The carrier-neutral core is privately operational and the first real-carrier adapter is repository-ready, but the platform is **not authorized for live SMS/MMS**. The shortest path to live carrier acceptance is now operational rather than architectural: obtain explicit carrier/provider approval, configure credentials and a DID privately, perform the public-webhook security/reachability changes under separate approval, then execute bounded live canary traffic with rollback and evidence capture.

## Deployment-tracking gap

`wwcx-messaging-gateway.service` is confirmed running live on Edge1 (see "Fresh ground truth" above), but unlike every other Edge1 service, this repository does not track its systemd unit file under `deploy/`. `services/wwcx-messaging-gateway/Containerfile` and `compose.test.yaml` define the CI/local containerized invocation (`uvicorn app.main:app --host 0.0.0.0 --port 8080`), but the live Edge1 deployment was observed at `/opt/wwcx-messaging-gateway-staging` as an "isolated runtime" (phase3-readiness-state.md) — it is not confirmed from repository evidence alone whether the live host runs the container image or a bare venv/uvicorn process, or what its exact `ExecStart`, working directory, or environment file look like. Authoring a tracked `deploy/messaging/wwcx-messaging-gateway.service` from repository evidence alone would risk documenting an invented invocation that does not match what is actually running. The safe next step is to capture the live unit's actual definition (`systemctl cat wwcx-messaging-gateway.service` or equivalent) from an authenticated Edge1 session first, then commit a unit file that matches it exactly — not to author one from assumption.
