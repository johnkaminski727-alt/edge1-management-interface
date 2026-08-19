# Edge1 / Project Big Bird live-state reconciliation — 2026-08-19

Status: current reconciliation record

This record supersedes older blanket statements that Edge1/Project Big Bird live deployment or health was wholly unverified. Historical acceptance records remain valid for their recorded checkpoints, but current claims must use the newest applicable evidence below.

## Evidence boundary

Evidence used for this pass:

- current GitHub `main` history;
- current authenticated read-only WW.CX Operations Console / Edge1 Operations Center surfaces backed by the Edge1 Operations API;
- canonical Project Big Bird Library records and current handoffs;
- prior accepted live evidence where a present-moment surface does not expose the same detail.

The direct ChatGPT `edge1.*` named-tool namespace was not mounted in the reconciliation conversation. Therefore exact present-moment `edge1.snapshot`, disk-state, configuration-digest, complete service/process, and Apache/Asterisk-internal outputs remain open rather than inferred.

## Repository versus deployed checkout

Repository checkpoint when this reconciliation was prepared:

- repository: `johnkaminski727-alt/edge1-management-interface`;
- branch: `main`;
- head: `888b6239a161102cc0381ba11dcda426a7929442`.

Current Edge1 Operations Center reports:

- production release branch: `main`;
- production checkout: `1534bb34fd38994db68a3142cb9156a07678e556`;
- repository state: clean.

GitHub comparison from deployed `1534bb34...` to `888b6239...` reports the repository head 193 commits ahead and 0 behind, with the deployed commit as the merge base. This proves clean ancestral source drift. It does not prove every running service is 193 commits stale because BigBird, Messaging, Communications and other components can use pinned or separate runtime trees.

Do not fast-forward production solely to make repository and deployed checkout numbers agree. Reconcile checkout-backed versus pinned/separate runtimes first and preserve rollback evidence.

## Current authenticated read-only operational state

Current WW.CX Operations Console observations:

- Edge1 Operations API: `ok`; 27 actions; mutations disabled.
- BigBird AI Gateway: read-only `0.3.4-alpha.3`; Library `ok`; 63 documents.
- BigBird tools: read-only; 8 tools.
- Messaging: `ok`.
- Numbering: `ok`; 2 prefixes; 1 source.
- Telephony: healthy; 0 alerts.
- Time Authority: healthy; consensus healthy; 10/10 sources.

Current Edge1 Operations Center observations:

- host: `edge1.ww.cx`;
- kernel: `6.1.0-52-amd64`;
- network posture available with four interfaces and WireGuard available;
- displayed operations/health/security/network/telephony/messaging/inventory/timeline timers active;
- overall status: **Attention Required** because current Suricata telemetry reports `unknown`, memory `0.0 GB`, and a security warning.

The current Suricata warning is a new read-only investigation item. It does not erase or reopen the separately accepted 2026-08-18 duplicate-runtime/OOM repair; determine whether the new warning is service state, collector/telemetry drift, or a new runtime defect before any restart or security change.

## Messaging Phase 3

Messaging Phase 3 private live readiness is complete at repository commit `888b6239a161102cc0381ba11dcda426a7929442`.

The acceptance record preserves:

- final reviewed source tree `c4f2f1f7d63e82c613186455ca7096ba1401034d`;
- runtime version `0.4.7`;
- loopback listener `127.0.0.1:58080`;
- PostgreSQL migrations `0001` through `0008`;
- exact runtime/source matching;
- simulator as the only provider;
- inbound, outbound and delivery workers disabled outside bounded acceptance;
- management mutation controls disabled;
- simulator outbound and persistent outbound policy disabled;
- no carrier/public traffic enabled.

Carrier selection, credentials, DIDs, public webhooks, production authentication/routing and live traffic remain separate authorization boundaries.

## Capacity

The 2026-08-19 host-capacity event is preserved as an accepted remediation record: the original 1 GiB swapfile was retained and a lower-priority 2 GiB `/swapfile2` was added, providing approximately 3 GiB total swap. Final Messaging acceptance reported approximately 1.5 GiB RAM available and approximately 2.2 GiB swap free at its sample point.

This capacity evidence does not supersede the current Suricata telemetry warning.

## Browser-visible Apache / telephony surfaces

- ordinary `https://edge1.ww.cx/` currently serves the Apache2 Debian default page;
- FreePBX Administration is reachable and identifies FreePBX 17.0.30;
- UCP is reachable at its login surface;
- authenticated Operations telemetry reports Telephony healthy with zero alerts.

These are visibility facts, not authorization to change Apache routing, FreePBX exposure, listeners, certificates, firewall policy or telephony routing.

## Superseded conclusions

The following older conclusions must not be used as current truth without checking their dated context:

- “live deployment and health remain unverified”;
- “no Edge1 shell/service inspection has been performed”;
- BigBird `0.3.4-alpha.2` as the current runtime;
- Messaging Phase 3 final live acceptance as outstanding;
- repository `main` checkpoints from 2026-08-17/18 as current heads.

## Current open verification items

1. Investigate the Suricata `unknown` / `0.0 GB` warning read-only before any restart or security mutation.
2. Capture direct named `edge1.*` tool outputs when the Operator namespace is mounted, especially snapshot, services, disk, Apache, Asterisk, git state and configuration digest.
3. Reconcile the clean 193-commit production-checkout ancestry deliberately, service by service, rather than by bulk fast-forward.
4. Reconcile ordinary Apache default-root and FreePBX/UCP exposure only under the existing Control Surfaces dependency/rollback plan.
5. Keep component version lines distinct: historical shared-hosting `v0.8.0e2/e3`, V4 Observatory, BigBird AI `0.3.4-alpha.3`, Messaging `0.4.7`, and other independently versioned services are not one linear release number.

## Safety boundary

No DNS, firewall, credential, authentication, certificate, production routing, public exposure, carrier activation, call/message traffic or production service restart was performed by this reconciliation. No secret values are recorded here.
