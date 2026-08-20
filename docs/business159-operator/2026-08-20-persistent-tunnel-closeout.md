# Business159 Authenticated Operator / Secure MCP Tunnel Closeout

Date: 2026-08-20  
Status: **OPERATIONALLY COMPLETE / PERSISTENT / ARCHIVE READY**  
Scope: Edge1-hosted Secure MCP Tunnel for the bounded Business159 shared-host operator and its Christmas Island Worldwide ChatGPT workspace packaging.

## Accepted architecture

`ChatGPT -> Business159 Operator tunnel -> Edge1 tunnel-client -> stdio business159-live-shell -> strict SSH -> Business159`

The accepted design keeps the Business159 runtime isolated from the Edge1 Operator and Big Bird tunnel namespaces and does not add a public MCP listener.

## Final host acceptance

The attended final verification on `edge1.ww.cx` completed successfully with:

- `business159-secure-mcp-tunnel.service` active;
- `business159-secure-mcp-tunnel.service` enabled at boot;
- controlled service restart succeeded;
- `Restart=on-failure` retained;
- `BUSINESS159_NODE_BIN=/opt/node-v24.18.0-linux-x64/bin/node` retained;
- `NODE_OPTIONS=--jitless` retained;
- `MemoryDenyWriteExecute=yes` retained;
- health URL remained loopback-only;
- `/healthz` returned `live`;
- `/readyz` returned `ready`;
- repository verifier returned `service_active=active`, `service_enabled=enabled`, `restart_policy=on-failure`, and `readyz=pass`;
- sibling services `edge1-operator-mcp.service`, `edge1-secure-mcp-tunnel.service`, and `bigbird-ai-tunnel.service` remained active/enabled;
- final operator marker: `BUSINESS159_PERSISTENT_TUNNEL=PASS`.

The earlier first-start Node/V8 failure was resolved without weakening `MemoryDenyWriteExecute`: the accepted source-controlled compatibility fix runs the Node v24 MCP child with `NODE_OPTIONS=--jitless`.

## Source-control acceptance chain

Relevant accepted repository milestones include:

- PR #465 — initial persistent Business159 Secure MCP Tunnel runtime;
- PR #467 — Node v24 runtime override support;
- PR #469 — permanent `--jitless` compatibility fix while retaining systemd executable-memory hardening;
- PR #472 — plugin package binding the Business159 authenticated-operator skill to the registered tunnel-backed app through `business159-live-shell`.

Repository source, runbooks, installers, validators, verifier, plugin package, and tests remain authoritative in `johnkaminski727-alt/edge1-management-interface`.

## ChatGPT workspace filing

Workspace filing reached the following accepted administrative state:

- custom app `Business159 Authenticated Operator` created against connection type `Tunnel` and tunnel `Business159 Operator`;
- app scan exposed 26 actions;
- app was enabled in the Christmas Island Worldwide workspace;
- repo-scoped plugin `Business159 Authenticated Operator` was packaged and installed by default in the workspace;
- plugin detail showed the Business159 app as `Required` and enabled;
- the obsolete standalone `business159-authenticated-operator` workspace skill was removed to avoid shadowing the plugin-bundled skill.

A fresh direct `business159_connection_test` result from the final archived ChatGPT session was not retained. The operator explicitly directed the closeout to proceed on the assumption that the ChatGPT-side acceptance works. This record therefore does **not** claim a separately captured final connector invocation that was not actually observed.

## Deferred residual: staged-filesystem smoke test

The runbook's staged-filesystem smoke sequence was **not performed** during this closeout. It must not be represented as passed.

Archive disposition:

- the persistent tunnel is operationally complete and accepted;
- the staged-filesystem smoke test is deferred and non-blocking for this archive closeout by operator direction;
- no temporary staged test file was created;
- no filesystem-mutation acceptance evidence is claimed;
- deployment apply and raw shell remain separately gated and are not implied by this closeout;
- future execution of the smoke sequence, if desired, must be treated as a new bounded acceptance activity with rollback and audit evidence.

## Security and secret-handling disposition

No tunnel ID, runtime API key, SSH private key, password, token, credential, or secret value belongs in Git, ChatGPT Library archive records, or this closeout document.

Secret-bearing runtime files remain local to Edge1 under their protected runtime/configuration paths. Archive records contain only non-secret architecture, state, metadata, source references, and acceptance results.

No DNS, certificate, firewall, SSH daemon/authentication-policy, public-listener, billing, telephony, SIP/carrier, alert-delivery, or unrelated production change is part of this closeout.

## Rollback / reopening boundary

Do not reopen this workstream merely because historical commissioning failures or the deferred filesystem smoke test exist. Reopen only for new contrary evidence, a requested filesystem/deployment capability acceptance, a tunnel/runtime failure, or a separately authorized hardening change.

If rollback is ever required, use the source-controlled Business159 tunnel runbook and preserve local protected configuration/evidence before disabling or removing runtime assets. Do not delete credentials or retained evidence as part of ordinary rollback.

## Archive disposition

This workstream is ready for archival with the following authority split:

- **GitHub:** maintained source, tests, plugin package, runbooks, and this closeout record;
- **Edge1:** live service/runtime configuration and protected secret material;
- **ChatGPT Library `/WW.CX/Edge1/Archives`:** non-secret closeout index and archive-ready evidence summary;
- **Airtable Operations Registry:** lifecycle/status metadata and durable source references only.

Final classification: **complete for persistent host/runtime deployment and workspace packaging; archive ready; staged-filesystem smoke deferred with no false pass claim.**
