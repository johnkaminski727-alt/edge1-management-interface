# WW.CX Mail Room Agent — Domain Lifecycle Management

Date: 2026-08-18  
Status: active product requirement; no production DNS, MX, provider, credential, or live-mail change is authorized by this document

## Objective

Adding, suspending, or retiring a mail domain must be a normal Mail Room administration workflow, not a source-code edit or a collection of unrelated manual changes.

The Mail Room must provide one controlled domain registry and lifecycle workflow that coordinates:

- domain identity and ownership metadata;
- legal entity and operating-name association;
- public sender identities and role addresses;
- private versus shared delivery routing;
- per-domain footer/disclaimer/compliance profiles;
- provider bindings;
- malware-scanning and attachment policy;
- inbound and outbound activation state;
- SPF, DKIM, DMARC, MX, and provider-readiness evidence;
- thread/reply continuity;
- audit, rollback, suspension, and retirement.

## Domain lifecycle states

A managed domain must have an explicit lifecycle state rather than a simple present/absent flag.

Recommended states:

- `staged` — registered in Mail Room but no live inbound or outbound mail flow is enabled;
- `inbound_ready` — configuration validates and inbound routing may be activated separately;
- `inbound_active` — authenticated inbound processing is active;
- `outbound_ready` — sender identities and policy validate but live sending is still disabled;
- `active` — authorized inbound and outbound functions are active according to their individual gates;
- `suspended` — new automatic processing/sending is disabled while configuration and history remain intact;
- `retiring` — no new outbound conversations are started; existing reply handling may continue according to a bounded retirement policy;
- `retired` — new live mail flow is disabled, but historical identity/thread records remain resolvable.

A domain must not disappear merely because it is no longer active. Historical correspondence must still be able to identify which domain, sender identity, legal entity, and policy applied at the time.

## Administration experience

The Operations Center / Mail Room should expose a dedicated **Domains** workspace.

For each domain it should show at minimum:

- domain name;
- lifecycle state;
- associated legal entity and operating name;
- inbound provider/binding state;
- outbound provider/binding state;
- private and shared delivery destination model;
- configured public identities and roles;
- footer/compliance profile;
- malware/security policy;
- SPF/DKIM/DMARC/MX readiness summary;
- active sender allowlist state;
- last validation time;
- warnings/blockers;
- last configuration change and actor.

The user should not need to edit JSON or application code for ordinary domain administration.

## Add-domain wizard

Adding a domain should be a staged wizard that is safe by default.

### Step 1 — Domain identity

Collect and validate:

- canonical domain name;
- legal entity;
- operating/trade name;
- website and privacy URL;
- public contact address;
- approved mailing address where required by policy;
- optional notes and internal ownership tag.

Creating the record must leave the domain in `staged` state.

### Step 2 — Delivery model

Choose the internal routing model without changing live provider routing:

- private John-address stream, when applicable;
- shared role-address stream;
- explicitly defined exceptions;
- unknown-recipient behavior, normally quarantine/reject rather than catch-all.

Internal delivery addresses such as `john-inbox@ww.cx` and `maildesk@ww.cx` remain implementation destinations and are not automatically exposed as public identities.

### Step 3 — Public identities

Add one or more named identities such as:

- `john@domain`;
- `contact@domain`;
- `support@domain`;
- `records@domain`;
- `accounts@domain`;
- `privacy@domain`;
- `regulatory@domain`;
- `postmaster@domain`;
- `abuse@domain`;
- other explicitly configured role identities.

Each identity must declare:

- display name;
- role/address class;
- internal delivery class;
- inbound eligibility;
- outbound eligibility;
- preferred/default status where applicable;
- footer/compliance overrides if any.

An arbitrary address must never become a live sender merely because it belongs to a managed domain.

### Step 4 — Compliance profile

Assign or create the approved domain/legal-entity profile used by the outbound composition engine.

The profile must resolve the correct:

- legal name;
- operating name;
- contact details;
- privacy URL;
- mailing address;
- confidentiality/records notice;
- commercial-message preference/unsubscribe behavior;
- role-specific legal or regulatory wording.

Legally material wording remains approved configuration and is not generated ad hoc by the AI.

### Step 5 — Security policy

Assign the Mail Room security profile, including:

- inbound malware scanning required;
- outbound malware scanning required;
- archive/decompression limits;
- attachment size/count limits;
- encrypted/password-protected attachment handling;
- remote-content suppression;
- HTML sanitization;
- quarantine behavior;
- optional domain-specific restrictions.

The default should inherit the system's strict fail-closed profile.

### Step 6 — Provider and DNS readiness

The system should perform read-only readiness checks where possible and display, without automatically changing production infrastructure:

- MX state;
- SPF state;
- DKIM selector/verification state;
- DMARC state;
- provider mailbox/alias presence when an authenticated provider adapter can safely confirm it;
- sender-verification state;
- inbound provider authentication state;
- expected envelope/bounce domain alignment.

Readiness checks do not authorize DNS, provider, mailbox, or routing changes.

### Step 7 — Validation

Before activation, run a deterministic configuration validation that confirms:

- domain is syntactically valid and unique;
- every identity is unique and maps to a valid internal destination;
- no private identity leaks into a shared route;
- sender selection is unambiguous;
- legal/footer profile resolves;
- malware/security profile resolves;
- no unknown provider binding is treated as active;
- outbound sender identities remain disabled unless explicitly verified/allowlisted;
- required SPF/DKIM/DMARC/provider gates are satisfied for any requested live outbound activation;
- route loops and catch-all hazards are absent.

Validation should produce a human-readable diff/preview of exactly what would change.

### Step 8 — Activation

Inbound and outbound activation are separate actions.

- Enabling inbound processing must not automatically authorize outbound sending.
- Enabling outbound sending must not automatically change MX or inbound routing.
- Provider/DNS changes, credentials, sender verification, and other privileged production operations remain separate explicit approval boundaries.

## Easy add behavior

For a normal staged domain, the expected administrator workflow should be approximately:

```text
Domains
  -> Add domain
  -> enter domain + legal entity
  -> choose delivery model
  -> select/create addresses
  -> choose compliance profile
  -> choose security profile
  -> review readiness
  -> Save staged domain
```

That operation must be reversible and must not send mail or alter DNS/provider settings by itself.

## Suspend and remove behavior

"Remove domain" must be intentionally safer than deleting a configuration object.

The normal workflow should be:

```text
active
  -> suspend
  -> review active conversations / inbound dependencies / aliases
  -> retire outbound
  -> optionally maintain bounded reply-only inbound handling during a retirement window
  -> retire inbound
  -> mark retired
```

### Suspension

Suspending a domain should immediately block new automatic outbound submission and optionally block or quarantine new inbound processing according to the selected action, without destroying configuration or history.

### Retirement

Retirement should preserve:

- historical message/thread correlation;
- original recipient and sender identity mappings;
- correspondence-control IDs;
- legal/footer profile version used for historical messages;
- audit records and scan dispositions;
- enough identity metadata to render old cases accurately.

A reply to an old conversation must never silently switch to another domain merely because the original domain has been retired. If that domain can no longer send, the system should block automatic transmission and require an explicit operator-selected migration/response identity.

### Hard deletion

Permanent deletion of a domain configuration should be exceptional.

It should be refused while any retained correspondence, case, audit, sender, routing, or compliance record still references the domain unless a separately authorized archival/migration process has resolved those dependencies.

Ordinary user-facing "Remove" should therefore mean `retire`, not destructive deletion.

## Domain configuration transaction model

Domain changes should be applied as validated transactions rather than partial edits across independent files.

A proposed domain change should produce a candidate configuration containing, at minimum:

```text
domain
legal_entity
operating_name
lifecycle_state
provider_bindings
internal_delivery_model
identities
sender_selection_rules
compliance_profile_id
security_profile_id
inbound_activation_state
outbound_activation_state
readiness_evidence
```

The system should then:

1. validate the candidate;
2. show a human-readable and technical diff;
3. persist the candidate only after confirmation by an authorized workflow;
4. record an append-only audit event;
5. retain the previous version as a rollback point;
6. reload only the bounded Mail Room configuration affected by the change;
7. verify post-change state.

No domain lifecycle operation should require a service-wide arbitrary shell command exposed to the browser or AI.

## Import/export and reuse

To make repeated onboarding easy, the Mail Room should support safe template-based configuration.

Useful templates may include:

- private/business domain;
- customer-support domain;
- telecommunications/regulatory domain;
- records/privacy domain;
- legacy/alias-only domain.

Templates may prepopulate roles and policies but must never carry provider credentials, DKIM private keys, passwords, API tokens, or other secrets.

The system should support exporting a redacted domain configuration package for review, backup, migration, and disaster recovery.

## Audit requirements

Every domain lifecycle change must record at least:

- domain;
- previous and new lifecycle state;
- configuration version/revision;
- actor/workflow identity;
- timestamp;
- fields changed or candidate diff hash;
- validation result;
- activation/deactivation result;
- rollback reference;
- whether any privileged provider/DNS action was required or remained pending.

Secrets and raw credential material must never enter the domain audit record.

## Mail Room agent behavior

The AI may:

- explain a domain's current configuration;
- identify missing identities or readiness checks;
- prepare a staged domain configuration;
- propose role addresses;
- run/read bounded validation results;
- explain why activation is blocked;
- prepare a retirement plan;
- compare domain configurations.

The AI must not infer authority to:

- change DNS/MX;
- provision provider mailboxes;
- create/rotate credentials or DKIM keys;
- enable live outbound sending;
- delete historical records;
- change legally material disclaimer wording;
- silently migrate old conversations to a different sender identity.

Those remain separately gated operations.

## Acceptance requirements

Do not call domain lifecycle management complete until tests prove:

1. a new domain can be added in `staged` state without source-code edits;
2. adding a domain does not enable live inbound or outbound mail automatically;
3. identities and routing can be added/removed through validated configuration transactions;
4. private/shared delivery separation is enforced for newly added domains;
5. every active sender resolves an approved compliance/footer profile;
6. every active domain resolves a malware/security profile;
7. readiness checks clearly distinguish configuration state from actual DNS/provider state;
8. inbound and outbound activation can be controlled independently;
9. a domain can be suspended immediately without losing configuration/history;
10. retirement blocks new outbound conversations while preserving historical thread identity;
11. historical replies never silently switch domains;
12. destructive deletion is rejected while retained records reference the domain;
13. every change has a rollback point and append-only audit evidence;
14. imported/template configurations cannot contain secrets;
15. the browser/AI never receives provider credentials, DKIM private keys, or arbitrary Mail Room shell access.

## Relationship to the multi-domain security requirements

This document extends `docs/messaging/mail-room-agent-multidomain-security-requirements-20260818.md`.

The existing managed domains remain valid starting entries, but the completed Mail Room must treat that list as dynamic administrative data rather than a permanently hard-coded product list.
