# WW.CX Unified Administration Control Centre

## Purpose

The Unified Administration Control Centre combines monitoring, analysis, investigation, governance, and controlled operations across the WW.CX administration estate. Browser code remains unprivileged and receives only sanitized, permission-filtered data.

## Information architecture

- **Command:** Operations Overview, Decision Centre, Change Control.
- **Observe:** Service Health, Logs & Events, VPN & Devices, Electrum Watch, Carrier Operations.
- **Analyze:** Analytics Workspace, Security, DNS, Telephony, Carrier, and Production analysis.
- **Control:** Firewall, DNS, service, carrier-request, carrier-review, and automation surfaces.
- **Govern:** Audit & Evidence, Configuration, and WW.CX AI.

## Product principles

1. Observe current state before presenting actions.
2. Display freshness, provenance, trend, and evidence.
3. Separate observation from privileged controls.
4. Require least privilege and independent permissions for navigation and actions.
5. Correlate drafts, approvals, execution, verification, rollback, and audit evidence.
6. Keep monitoring usable on mobile while requiring expanded review for privileged work.

## Control transaction model

Privileged changes use this server-side lifecycle:

```text
request -> authorization -> current-state capture -> draft -> validation
        -> impact preview -> approval -> execution -> verification
        -> evidence -> close or rollback
```

Required records include the actor, approver, target environment, resources, purpose, requested operation, before-state digest, validation output, impact assessment, rollback method, execution result, verification checks, and final evidence location.

The browser must never receive SSH keys, wallet credentials, API secrets, sudo credentials, unrestricted RPC, or shell capability.

## Domain boundaries

- **Electrum:** watch-only and read-only health, wallet state, balances, synchronization, and sanitized connectivity. No signing, broadcasting, wallet mutation, private material, or arbitrary commands.
- **Carrier Operations:** carrier-scoped exported summaries only.
- **Carrier Requests:** ticket and change-request intake only; submission is not approval or execution authority.
- **Carrier Review:** acknowledgement and review lifecycle only; no production authorization or execution.
- **Firewall and DNS:** structured draft, validation, impact preview, approval, bounded execution, verification, and rollback.

## Analytics

Analytics must produce evidence-backed findings with baseline, deviation, severity, confidence, affected scope, likely contributors, recommended action, and operational risk. Initial detectors cover service latency, firewall block changes, authentication failures, DNS errors, VPN staleness, telephony or carrier degradation, unusual administrative activity, and stale data sources.

## Roles

Representative roles are `executive_viewer`, `operations_viewer`, `operations_analyst`, `change_author`, `change_approver`, `operator`, `security_administrator`, `system_administrator`, and `auditor`. An author must not silently approve their own privileged change.

## Delivery phases

1. Unified registry, navigation shell, common components, permission filtering, and audit correlation.
2. Read-only health, logs, network, DNS, firewall, VPN, Electrum, carrier, telephony, and production adapters.
3. Change-control API with firewall and DNS draft, validate, preview, approve, verify, and rollback workflows.
4. Approved automation, anomaly detection, incident linkage, SLO reporting, forecasting, and periodic access reviews.

## Acceptance criteria

- All verified administration routes appear under predictable navigation.
- Every module declares route, capability, permission, risk, and visualization.
- Monitoring surfaces display freshness and provenance.
- Analytics include baseline comparisons and evidence-backed findings.
- Privileged changes cannot bypass validation, approval, verification, audit, or rollback metadata.
- Responsive navigation is keyboard accessible.
- No secret or unrestricted command capability is exposed to the browser.
