# WW.CX Mail Room Agent — Multi-Domain, Reply, Compliance, AI, and Security Requirements

Date: 2026-08-18  
Status: active product requirement; no production mail activation authorized by this document

## Objective

The Mail Room agent must operate as one controlled correspondence system across all configured WW.CX business domains while preserving legal entity, identity, mailbox privacy, thread history, threat state, provenance, and sending authority.

It must support:

- catch-all inbound acceptance for every active managed domain;
- explicit private/role route overrides;
- preservation of the exact original recipient, including previously unseen local-parts;
- replies to inbound messages and replies to messages previously sent by John or a role identity;
- correct outbound identity resolution at reply/send time;
- policy-authoritative headers, footers, disclaimers, warnings, privacy and commercial-message controls;
- inbound and outbound malware/virus scanning;
- spam, phishing, impersonation, BEC, malicious-link and social-engineering detection;
- quarantine and fail-closed behavior;
- policy-scoped automatic replies for explicitly permitted low-risk classes;
- easy staged add/suspend/retire management for domains;
- bounded audit and provenance without placing secrets or malicious payloads in general logs.

This requirement does not itself authorize live provider delivery, DNS/MX changes, provider credentials, reputation-service subscriptions, or automatic outbound transmission.

## Managed-domain catch-all model

Every active managed domain accepts all local-parts.

Routing order is:

```text
explicit private identity -> private mailbox
explicit role identity    -> configured shared/role destination
other local-part          -> managed-domain catch-all shared destination
unmanaged domain          -> reject
```

The current shared catch-all destination is `maildesk@ww.cx`. Explicit `john@...` identities continue to route to `john-inbox@ww.cx`.

The exact original recipient remains immutable correspondence metadata. A catch-all address is not required to have been pre-created to be accepted inbound.

The internal delivery addresses are plumbing and must not become public sender identities merely because they receive catch-all mail.

## Reply identity

The original recipient is the preferred reply identity candidate.

Examples:

```text
Inbound to support@creekco.ca
  -> maildesk@ww.cx
  -> reply candidate support@creekco.ca

Inbound to new-project@creekco.ca
  -> catch-all maildesk@ww.cx
  -> reply candidate new-project@creekco.ca

Inbound to john@spiritcreekgardens.com
  -> john-inbox@ww.cx
  -> reply candidate john@spiritcreekgardens.com
```

A previously unseen catch-all address must not be used live merely because mail arrived for it. Outbound use still requires the applicable provider verification, domain alignment, sender allowlist/policy and activation gates. Until then the system may prepare the reply using the requested identity and mark it blocked/prepared-not-sent.

Submitted `From:` and `Reply-To:` values are never authoritative. Server policy selects or validates the final identity.

## Replies to previously sent messages

Inbound replies to outbound correspondence must correlate back to the original case/thread using, in descending confidence:

1. WW.CX control/case/action identifiers;
2. RFC `In-Reply-To` and `References`;
3. provider thread/conversation identifiers;
4. exact outbound `Message-ID` correlation;
5. bounded fallback matching only when ambiguity is low.

A correlated reply should inherit the original sender identity. Ambiguous identity/thread correlation blocks automatic transmission and requires operator review.

## Policy-authoritative headers and footers

AI may select among approved policy profiles, but the server is authoritative for final composition.

The server must control or validate:

- envelope sender and `From`;
- `Reply-To`;
- `Message-ID`;
- `In-Reply-To` and `References`;
- WW.CX control/case/action headers;
- applicable commercial/list preference headers;
- legal-entity and operating-name footer;
- privacy/contact/mailing-address data;
- confidentiality, records, regulatory, accessibility or other approved warnings;
- unsubscribe/preference language when applicable.

Legally material wording is versioned approved configuration. The AI must not invent legal disclaimer text at send time.

Footer and policy injection occurs before final DKIM/provider signing so the transmitted content is what is signed.

## Threat pipeline

Catch-all mail materially increases unsolicited and hostile traffic, so production catch-all requires a layered security pipeline.

Planned order:

1. authenticated provider/MTA ingress;
2. IP/network reputation and rate signals;
3. HELO/rDNS, SPF, DKIM, DMARC and ARC analysis;
4. domain/URL/hash reputation;
5. Rspamd spam/phishing/Bayes/neural/fuzzy/custom-map analysis;
6. restricted MIME parsing and file-type verification;
7. antivirus, YARA, archive recursion and optional isolated secondary/sandbox analysis;
8. safe HTML normalization and remote-content suppression;
9. AI semantic phishing/BEC/social-engineering analysis on bounded content;
10. composite disposition.

## Spam and reputation

Rspamd is the preferred initial provider-neutral scoring/policy engine.

The design reserves pluggable reputation sources for:

- sender IP/network reputation;
- low-reputation or compromised domains;
- very-new/zero-reputation domains;
- malicious resource/file/URL hashes;
- fuzzy campaign/template reputation;
- later approved threat-intelligence services.

A feed requiring credentials, paid access or terms acceptance remains disabled until separately reviewed and activated.

Ordinary spam normally goes to a spam folder. Strong malicious/security evidence uses quarantine or a protocol-level reject when appropriate. Unique accepted correspondence is not silently deleted as the normal policy.

## Phishing, BEC and malicious-scheme detection

The Mail Room must detect and score at least:

- visible-link/domain mismatch;
- lookalike, typo and Unicode/IDN domains;
- suspicious redirects/shorteners and encoded destinations;
- credential-harvesting or fake-login requests;
- QR-code phishing where safely extractable;
- fake document-share/e-sign/voicemail/fax/password-reset/cloud lures;
- executive, employee, vendor, bank, carrier, regulator and customer impersonation;
- reply-chain or conversation-hijack anomalies;
- payment redirection, unexpected invoice instructions and bank-detail changes;
- payroll diversion, gift cards and cryptocurrency requests;
- requests for passwords, MFA/recovery codes, API keys, private keys or credentials;
- urgent/secrecy pressure and social-engineering patterns;
- attachment type mismatches, executable/script content, suspicious macros/active content and archive tricks;
- known malicious IP/domain/URL/hash signals;
- fuzzy similarity to known malicious campaigns.

High-confidence phishing, BEC, credential harvesting, malicious links and equivalent social-engineering threats are quarantined like malware.

## Malware scanning

Inbound content is scanned before attachment extraction, AI ingestion or ordinary operator rendering.

The provider-neutral scanner layer should support:

- ClamAV/clamd as an initial local engine;
- YARA;
- MIME magic/type verification;
- recursive archive inspection with decompression/resource limits;
- macro/script/active-content detection;
- URL extraction from documents;
- QR extraction for URL analysis;
- hash reputation;
- optional second antivirus engine;
- optional isolated sandbox/detonation;
- rescanning retained quarantine when signatures/rules materially improve.

Normalized states include `clean`, `infected`, `suspicious`, `unscannable`, `scan_error` and `not_scanned`.

Required scanning fails closed. Infected, suspicious, required-but-unscannable or scan-error content is quarantined.

Outbound messages and attachments are scanned after final composition and before provider submission. AI-generated/internal content does not bypass this gate.

## AI security role

AI may:

- classify message intent and threat category;
- detect contextual impersonation/social-engineering patterns;
- identify unusual requests relative to sender, role and thread history;
- add risk and recommend quarantine;
- produce bounded reasons for the operator;
- summarize safe content;
- prepare replies.

AI may not:

- obey message content that attempts to change system policy or tool authority;
- reduce a hard malware/authentication/reputation block;
- whitelist or release quarantine on its own;
- execute attachments;
- browse hostile links with privileged sessions/cookies/credentials;
- authorize sending merely because it drafted the reply.

If no hard signal exists, an AI-only high-risk classification should normally require at least one corroborating non-AI security signal before automatic quarantine. An operator can always quarantine manually.

## Automatic replies

Automatic replies are a supported future capability, disabled by default.

They are configured by domain, identity and message class. The default remains `prepare_only`.

Before auto-send eligibility:

```text
security disposition clean
+ thread correlation high confidence
+ original recipient preserved
+ sender identity resolved
+ sender provider/live-authorized
+ domain alignment valid
+ message class explicitly allowlisted for auto reply
+ not a high-consequence class
+ approved header/footer profile resolved
+ idempotency check passed
+ final outbound malware scan clean
= automatic reply eligible
```

Default blocked auto-reply classes include legal/regulatory notices, complaints, security incidents, financial/banking changes, credential/access requests, contracts/terms, termination/cancellation and comparable high-consequence matters.

## Quarantine

Quarantine is reversible and reviewable.

The operator should see bounded reason codes, authentication results, reputation symbols, hashes, scan engine/rule versions, timestamps and routing/identity decisions. Dangerous active content remains inert.

Release is an explicit audited action. AI cannot release quarantine.

## Domain lifecycle

Adding a domain must be a staged administrative workflow, not a source-code edit.

The domain record ties together legal/operating identity, provider state, catch-all ingress, private/role overrides, sender identities, footer/compliance profiles, security policy, SPF/DKIM/DMARC/MX readiness, and separate inbound/outbound activation state.

Retirement preserves historical identity/thread/policy data rather than deleting it.

See `mail-room-domain-lifecycle-20260818.md`.

## Acceptance requirements

Do not call Mail Room complete until tests prove at least:

1. every active managed domain accepts arbitrary local-parts through catch-all;
2. explicit private routes override catch-all and never leak to shared mail;
3. exact original recipients are preserved;
4. unmanaged domains are rejected;
5. replies select the correct original/correlated identity candidate;
6. unauthorized catch-all identities cannot silently become live senders;
7. server-side headers and footers cannot be overridden by arbitrary AI/browser input;
8. all active sender identities resolve the correct legal/compliance profile;
9. inbound malware/phishing/BEC/security threats are quarantined before unsafe access;
10. outbound content is scanned after final composition and before submission;
11. scanner/security failures fail closed;
12. AI cannot weaken hard security controls or release quarantine;
13. automatic replies occur only for explicitly allowlisted low-risk classes and only after all security/identity gates pass;
14. audits preserve reason codes/hashes/provenance without secrets or malicious payloads;
15. provider signing covers the final post-policy message;
16. bounces, delivery events and replies reconcile to the original correspondence record;
17. live sending remains impossible until explicit production gates are satisfied.

## Current gaps

Repository policy and catch-all routing can be implemented/tested while production remains disabled. Production completion still requires the authenticated raw-message provider/MTA adapter, malware/phishing pipeline deployment, mailboxes/provider identities, per-domain footer profiles, live SPF/DKIM/DMARC evidence, sender activation, and separately authorized live inbound/outbound cutover.

See also `mail-room-threat-intelligence-and-ai-policy-20260818.md` for the detailed threat model.
