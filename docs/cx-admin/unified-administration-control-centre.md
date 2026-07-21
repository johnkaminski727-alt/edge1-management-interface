# WW.CX Unified Administration Control Centre

## Purpose

The Unified Administration Control Centre turns the website administration area into a coherent operational workspace for monitoring, analysis, investigation, and controlled change. It integrates existing WW.CX and Big Bird administration routes without granting browser code direct privileged access to production systems.

## Product principles

1. **Observe before acting.** Every control page begins with current state, freshness, provenance, and health.
2. **Explain change.** Analytics show trends, anomalies, correlations, and likely causes rather than raw counters alone.
3. **Stage before applying.** Firewall, DNS, service, routing, certificate, and access changes use draft, validate, review, approve, apply, verify, and rollback stages.
4. **Least privilege.** Navigation and actions are filtered independently by role and permission.
5. **Audit everything.** Read, draft, approval, execution, verification, rollback, and export events share a correlation ID.
6. **Progressive disclosure.** Executives see posture and risk; operators can drill into evidence and controls.
7. **Mobile-safe operations.** Monitoring remains useful on small screens; destructive or privileged actions require an expanded review surface.

## Information architecture

### Command

- **Operations Overview** — estate health, unresolved incidents, change queue, capacity, and recent anomalies.
- **Decision Centre** — prioritized findings, recommended actions, confidence, impact, and owner.
- **Change Control** — drafts, validation results, approvals, execution state, rollback readiness, and evidence.

### Observe

- **Service Health** — service state, listeners, endpoint checks, dependencies, and freshness.
- **Network & Traffic** — traffic volume, latency, errors, sources, destinations, and protocol mix.
- **Logs & Events** — correlated operational, application, security, and audit events.
- **VPN & Devices** — device posture, tunnel state, handshake freshness, address allocation, and access scope.

### Analyze

- **Analytics Workspace** — time-series comparisons, baselines, cohort filters, correlations, and exports.
- **Security Analysis** — threat signals, blocked traffic, authentication anomalies, and policy effectiveness.
- **DNS Analysis** — query volume, response codes, cache performance, latency, domains, and resolver health.
- **Telephony Analysis** — call and messaging quality, routing outcomes, carrier performance, and fraud indicators.
- **Production Analysis** — print and other operational production throughput, errors, backlog, and SLA performance.

### Control

- **Firewall Control** — inspect effective policy, simulate impact, stage bounded rule changes, validate syntax, approve, apply, verify, and roll back.
- **DNS Control** — inspect zones and resolver state, stage record or policy changes, validate, compare, approve, apply, verify, and roll back.
- **Service Control** — inspect units and dependencies; stage bounded restart, reload, enablement, or deployment operations.
- **Access Control** — users, roles, permissions, sessions, API clients, and privileged-action policy.
- **Automation** — scheduled checks and approved runbooks with dry-run and evidence capture.

### Govern

- **Audit & Evidence** — immutable action timeline, actor, purpose, before/after state, validation, outcome, and evidence links.
- **Configuration** — non-secret feature settings, thresholds, retention, integrations, and display preferences.
- **System Registry** — modules, routes, capabilities, dependencies, ownership, status, and documentation.

## Page pattern

Every operational page should use the same hierarchy:

1. page title, purpose, environment, and data freshness;
2. posture summary with health, risk, and outstanding action counts;
3. primary visualization appropriate to the domain;
4. findings and recommendations with confidence and evidence;
5. searchable and filterable detail table;
6. change controls, when permitted, separated from observation;
7. audit and provenance footer.

## Visual language

- Status cards communicate health, freshness, and trend, never health alone.
- Time-series charts use consistent periods and comparison baselines.
- Heat maps are reserved for density, geography, time-of-day, or matrix relationships.
- Sankey or flow diagrams are appropriate for traffic, routing, and processing paths.
- Topology diagrams display systems and dependencies, not decorative network art.
- Tables remain the authoritative detail view and support export.
- Risk uses text and iconography in addition to colour.

## Control transaction model

Privileged controls must use a server-side transaction envelope:

```text
request -> authorization -> current-state capture -> draft -> validation
        -> impact preview -> approval -> execution -> verification
        -> evidence record -> close or rollback
```

Required fields:

- change ID and correlation ID;
- actor and approving actor;
- target environment and resources;
- purpose and ticket or project reference;
- requested operation and bounded parameters;
- before-state digest;
- validation output;
- impact assessment;
- rollback method and readiness;
- execution output and exit status;
- verification checks;
- final state and evidence location.

The browser must never receive SSH keys, API secrets, sudo credentials, or unrestricted shell capability. Firewall and DNS actions should call narrowly scoped authenticated backend operations.

## Firewall control design

The firewall workspace contains:

- effective ruleset and source-of-truth identifier;
- counters, top blocked sources, destination/service distribution, and trend;
- rule search and dependency references;
- proposed-rule editor using structured fields rather than free-form shell;
- syntax validation and policy simulation;
- duplicate, shadowed, broad, and lockout-risk detection;
- explicit management-path preservation check;
- approval, apply, post-change connectivity verification, and rollback.

No production firewall change is automatic merely because it was drafted in the UI.

## DNS control design

The DNS workspace contains:

- managed zones, authoritative servers, resolver health, serials, and DNSSEC state;
- query analytics, latency, response-code mix, cache hit rate, and notable domains;
- record inventory and history;
- staged record editor with TTL, type, target, and validation;
- zone linting, duplicate/conflict checks, delegation checks, and propagation plan;
- approval, apply, authoritative verification, external verification, and rollback.

## Analytics and decision support

Analytics should produce findings, not just charts. Each finding contains:

- observation and affected scope;
- baseline and deviation;
- confidence and severity;
- likely contributing factors;
- evidence links;
- recommended next action;
- whether the action is informational, reversible, privileged, or prohibited without explicit approval.

Initial detectors:

- service availability or latency regression;
- sudden firewall block-rate change;
- repeated authentication failure clusters;
- DNS error-rate, cache, or latency regression;
- VPN handshake staleness;
- telephony quality or carrier-route degradation;
- unusual administrative changes;
- data source staleness or collection failure.

## Roles

- `executive_viewer`: posture, trends, findings, reports.
- `operations_viewer`: detailed monitoring, logs, evidence, exports.
- `operations_analyst`: saved analyses, annotations, recommendations.
- `change_author`: drafts and validates bounded changes.
- `change_approver`: approves eligible changes but cannot silently author and approve the same change.
- `operator`: executes approved bounded operations.
- `security_administrator`: security policy and access governance.
- `system_administrator`: module configuration and registry management.
- `auditor`: read-only access to audit and evidence.

## Delivery phases

### Phase 1 — Foundation

- unified navigation registry and capability model;
- responsive shell and operations overview prototype;
- common page components and data contracts;
- role/permission filtering;
- audit correlation model.

### Phase 2 — Observation and analysis

- health, logs, network, DNS, firewall, VPN, telephony, and production data adapters;
- analytics workspace and finding model;
- freshness and provenance indicators;
- exports and saved views.

### Phase 3 — Safe controls

- change-control API and evidence store;
- firewall and DNS draft/validate/preview workflows;
- approval separation;
- bounded execution adapters;
- post-change verification and rollback.

### Phase 4 — Operational maturity

- automation and runbook execution;
- anomaly detection and recommendations;
- incident linkage;
- SLO and capacity forecasting;
- periodic access and policy reviews.

## Acceptance criteria

- all verified administration routes appear under one predictable navigation system;
- each module declares owner, capability, route, permission, maturity, data sources, and control risk;
- monitoring pages display freshness and provenance;
- analytics pages provide at least one baseline comparison and one evidence-backed finding;
- privileged changes cannot bypass validation, approval, verification, audit, or rollback metadata;
- responsive navigation and core dashboards meet keyboard and screen-reader expectations;
- no secret or unrestricted command capability is exposed to the browser;
- validators reject duplicate routes, duplicate module IDs, invalid capabilities, and control modules without explicit risk and permission metadata.
