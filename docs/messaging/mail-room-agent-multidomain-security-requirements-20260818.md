# WW.CX Mail Room Agent — Multi-Domain, Reply, Compliance, and Malware Requirements

Date: 2026-08-18  
Status: active product requirement; no production mail activation authorized by this document

## Objective

The Mail Room agent must operate as one controlled correspondence system across the managed WW.CX business domains while preserving the identity, legal entity, mailbox privacy, thread history, security state, and sending authority appropriate to each message.

It must support:

- inbound processing for all configured domains and named recipient identities;
- private versus shared mailbox separation;
- replies to both inbound messages and replies to messages originally sent by John or an authorized role identity;
- automatic selection of the correct outbound identity;
- per-domain/per-identity footer, disclaimer, warning, privacy, and commercial-message policy;
- inbound and outbound malware/virus scanning before content or attachments are trusted;
- quarantine and fail-closed behavior when scanning or identity resolution is uncertain;
- bounded audit and provenance without placing secrets or raw message bodies in general audit logs.

This requirement does not authorize live provider delivery, DNS/MX changes, provider credentials, or outbound sending.

## Managed domains

The existing identity registry is authoritative for these managed domains:

- `ww.cx`
- `creekco.ca`
- `spiritcreekgardens.com`
- `scgardens.ca`
- `omegafx.com`

The registry remains the source of truth for approved public identities, legal/operating names, private John identities, role identities, and sender eligibility.

## Mailbox privacy model

The existing separation remains mandatory:

- `john-inbox@ww.cx` is the private internal delivery target for `john@...` identities;
- `maildesk@ww.cx` is the shared internal delivery target for company/role identities;
- `noreply@ww.cx` is outbound-only and may be used only for explicitly system-generated messages that should not invite replies.

The internal delivery mailboxes must not become public sender identities or catch-all addresses.

## Identity-aware inbound and reply handling

For every accepted inbound message, the processing record must preserve at least:

- authenticated provider/source identifier;
- original envelope recipient;
- normalized `To`, `Cc`, and sender metadata;
- provider message identifier and RFC `Message-ID` when available;
- `In-Reply-To` and `References` when available;
- WW.CX control/case/action identifiers when present;
- received timestamp and immutable content/attachment hashes;
- malware-scan status;
- route decision and destination mailbox;
- thread/conversation correlation identifier.

The original recipient must remain authoritative when selecting the reply identity.

Examples:

```text
Inbound to john@spiritcreekgardens.com
  -> private mailbox
  -> reply from john@spiritcreekgardens.com

Inbound to support@creekco.ca
  -> shared role mailbox
  -> reply from support@creekco.ca

Inbound to records@omegafx.com
  -> shared role mailbox
  -> reply from records@omegafx.com
```

Unknown managed-domain recipients remain quarantined rather than silently routed through a catch-all.

## Replies to messages originally sent by John or a role identity

The Mail Room agent must also accept and correlate inbound replies to outbound correspondence.

Thread correlation should use, in descending order of confidence:

1. WW.CX control/case/action identifiers carried in protected message metadata;
2. provider/RFC `In-Reply-To` and `References` relationships;
3. provider conversation/thread identifiers;
4. exact known outbound `Message-ID` correlation;
5. bounded fallback matching only when ambiguity is low.

A reply to an outbound message must inherit the original sender identity unless an explicit authorized workflow changes it.

For example, a reply to mail sent from `regulatory@creekco.ca` should return to the CreekCo regulatory correspondence stream and any later response should default to `regulatory@creekco.ca`, not `john@ww.cx` or a generic shared mailbox address.

Ambiguous thread/identity correlation must fail closed for automatic sending and be surfaced for operator review.

## Authoritative outbound sender selection

Submitted `From:` and `Reply-To:` headers remain untrusted input.

The server-side identity policy must select the sender using the existing model:

1. explicit system-generated mode -> `noreply@ww.cx`;
2. preserved original recipient -> matching sender identity;
3. approved identity hint -> registered non-system sender;
4. controlled default only where policy permits.

Unknown original recipients or identities must be rejected rather than guessed.

Live sending remains blocked unless the exact sender is provider-verified, domain-aligned, present in the live sender allowlist, and the applicable SPF/DKIM/DMARC and provider activation gates have passed.

## Per-domain and per-identity disclaimer policy

The existing single WW.CX organization footer is not sufficient as the final multi-domain model.

Before live multi-domain sending, the footer/compliance engine must resolve an approved profile from:

```text
selected sender identity
  -> managed domain/legal entity
  -> message class
  -> optional role-specific requirements
```

The resolved profile may include, as applicable and pre-approved:

- correct legal entity name;
- operating/trade name;
- correct website and privacy URL;
- approved mailing address;
- public contact address appropriate to the sending identity;
- confidentiality/records notice;
- non-creation-of-rights caveat;
- transparent correspondence-control disclosure;
- commercial-message unsubscribe/preference language where required;
- role-specific notices for regulatory, accessibility, billing, support, records, or other governed correspondence.

The system must never assume that a WW.CX disclaimer is legally or operationally appropriate for CreekCo, Spirit Creek Gardens, OmegaFX, or another sender merely because the message is processed by the same Mail Room service.

Legal/compliance wording must be treated as approved configuration, not generated ad hoc by the agent. Changes to legally material disclaimer text require separate review/authorization.

Footer injection must occur before final message signing/submission so DKIM or provider signing covers the actual transmitted content.

## Message classes

The current message classes remain useful starting categories:

- `business_correspondence`
- `commercial`
- `legal_notice`
- `support`

The Mail Room agent may classify or recommend a class, but legally significant classifications must be overrideable and auditable. The selected class controls the applicable footer/disclaimer policy and whether an unsubscribe/preference mechanism is mandatory.

## Inbound malware and virus scanning

The Mail Room agent must not expose unscanned inbound attachments or active content to the AI, operator browser, archive pipeline, or downstream automation.

The inbound adapter must acquire the raw message in a restricted temporary/quarantine area and perform security processing before normal delivery. At minimum:

1. enforce total message, part, attachment-count, and decompression limits;
2. calculate SHA-256 for raw message and each attachment;
3. validate declared MIME type against observed content where practical;
4. scan raw message parts and attachments with an approved anti-malware engine;
5. inspect common archive/container formats using bounded recursive extraction;
6. treat encrypted/password-protected or unsupported containers as `unscannable` unless separately approved;
7. sanitize or neutralize active HTML before operator/AI rendering;
8. block automatic loading of remote content/tracking resources in previews;
9. quarantine infected, suspicious, malformed, scan-error, or unscannable content according to policy;
10. record scan engine/version, signature/database version, timestamps, hashes, and disposition without copying malicious payloads into general logs.

Recommended normalized scan states:

- `clean`
- `infected`
- `suspicious`
- `unscannable`
- `scan_error`
- `not_scanned`

Only `clean` content should be eligible for automatic attachment extraction or AI ingestion.

## Outbound malware and virus scanning

All outbound messages must be scanned after final composition and before provider submission.

This includes:

- generated body variants;
- user-provided body content where applicable;
- every attachment;
- generated documents or archives;
- final MIME/package representation where the adapter makes it available.

Outbound policy must fail closed if an attachment or composed message is `infected`, `suspicious`, `unscannable` where scanning is required, or `scan_error`.

A blocked outbound item must remain `prepared_not_sent` or enter a dedicated quarantine/blocked state. The Mail Room agent must not bypass the scanner because the content was generated internally or supplied by an administrator.

## Malware scanning implementation boundary

The repository does not currently contain a complete mail antivirus pipeline. The current inbound hub stores routing metadata/hashes rather than raw MIME/attachment bytes, so malware scanning requires a provider/MTA adapter or restricted pre-delivery staging layer that has access to the actual message content.

An initial implementation should use a provider-neutral scanner interface so the policy is not tied to one product. A typical first engine may be ClamAV/clamd, with optional additional YARA/reputation/sandbox adapters later. Engine choice and host deployment remain separate operational decisions.

The scanning service must not require the AI process itself to parse potentially malicious files before the scanner has cleared them.

## Safe AI access

Mail content is untrusted data even after malware scanning.

The AI may summarize, classify, extract tasks, prepare replies, and propose routing only within the caller's mailbox/content scope. Retrieved message text cannot grant new scopes, change system policy, authorize sending, or cause attachment execution.

Attachments should be offered to AI/document processing only after `clean` disposition and through bounded parsers appropriate to the file type.

## Sending and approval model

A complete Mail Room may eventually support an explicit scoped send action, but draft preparation and automatic reply composition do not imply permission to transmit.

Until separately activated, outbound preparation remains `prepared_not_sent`.

When send is later enabled, the pipeline must require all of the following before submission:

```text
identity resolved
+ sender live-authorized
+ domain/provider alignment valid
+ footer/disclaimer profile resolved
+ message policy valid
+ malware scan clean
+ attachment policy valid
+ idempotency check passed
+ explicit workflow authorization satisfied
= eligible for provider submission
```

## Acceptance requirements

Do not call the Mail Room agent complete until tests prove:

1. all configured managed domains route correctly;
2. private John identities never leak into the shared mailbox;
3. role identities route to the shared mailbox without losing original-recipient metadata;
4. replies to inbound messages use the same public identity that received them;
5. inbound replies to previously sent messages correlate back to the correct thread/case and identity;
6. an arbitrary submitted `From:`/`Reply-To:` cannot override server policy;
7. every active sender resolves the correct approved legal/footer profile;
8. commercial-message policy fails closed when required preference/unsubscribe data is missing;
9. inbound infected/suspicious/unscannable content is quarantined before AI/operator attachment access;
10. outbound infected/suspicious/unscannable content is blocked before provider submission;
11. scanner failures fail closed rather than silently bypassing security;
12. audit records contain hashes, routing/identity decisions, scan results, control IDs, and provider state without storing secrets or malicious payloads in general logs;
13. DKIM/provider signing, when activated, covers the final post-footer message;
14. bounces, provider delivery events, and replies can be reconciled to the original correspondence control record;
15. live sending remains impossible unless all explicit production gates are satisfied.

## Current gaps to close

The current project already has strong multi-domain routing and sender-selection foundations, but the following remain required before this design is production-complete:

- provider mailbox provisioning and authenticated inbound content adapter;
- full message/thread/reply reconciliation for outbound-originated conversations;
- per-domain/per-identity legal/footer policy profiles rather than one global WW.CX organization footer;
- inbound raw-content/attachment staging suitable for scanning;
- provider-neutral malware scanner interface and quarantine implementation;
- outbound final-message/attachment scanning gate;
- safe HTML rendering and remote-content suppression for message previews;
- live provider sender verification and SPF/DKIM/DMARC activation evidence;
- explicit authorization for any production send or provider/DNS cutover.
