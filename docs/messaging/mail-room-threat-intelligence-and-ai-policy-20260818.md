# WW.CX Mail Room — AI, Spam, Phishing, and Threat-Intelligence Policy

Date: 2026-08-18  
Status: staged product/security requirement; no live mail or external reputation service activation authorized by this document

## Objective

The Mail Room must treat unsolicited mail, phishing, impersonation, credential harvesting, business-email compromise, malicious links, malware, and other social-engineering schemes as security events that can be quarantined before they reach normal operator or AI workflows.

The architecture is deliberately layered. No single AI model, antivirus engine, DNS blocklist, or heuristic is authoritative by itself for every decision.

## Security pipeline

For inbound mail, use these stages in order:

1. authenticated provider or trusted MTA ingress;
2. connection/IP reputation and rate signals where available;
3. envelope, HELO/rDNS, SPF, DKIM, DMARC, and ARC analysis;
4. domain, URL, redirector, hash, and campaign reputation;
5. Rspamd spam/phishing/Bayes/neural/fuzzy/custom-map analysis;
6. restricted MIME parsing and attachment-type validation;
7. antivirus, YARA, archive recursion, and optional isolated secondary/sandbox analysis;
8. safe HTML normalization, remote-content suppression, and URL extraction;
9. AI semantic threat analysis on already-bounded content;
10. composite disposition: deliver, spam folder, quarantine, reject at an appropriate protocol boundary, or operator review.

For outbound mail, scan the final post-footer/post-header composition before provider submission. Internal or AI-generated content does not bypass security scanning.

## Managed-domain catch-all interaction

All local-parts at an active managed domain are accepted by the Mail Room unless a more specific explicit route applies. The exact original recipient is preserved as immutable correspondence metadata.

Explicit private identities such as `john@...` retain their private mailbox route. Other explicitly registered role identities retain their configured route. An otherwise unknown local-part at a managed domain falls back to the shared Mail Room destination rather than being discarded solely because the address was not pre-created.

Catch-all acceptance increases exposure to random-address and dictionary spam, so threat filtering, rate controls, reputation, and quarantine are mandatory parts of the eventual production path.

An unmanaged domain is still rejected.

## Rspamd role

Rspamd is the preferred provider-neutral spam and message-risk policy engine for the initial implementation. Planned capabilities include:

- SPF, DKIM, DMARC, and ARC results;
- DNS/RBL reputation queries;
- Bayes classification;
- neural classification where the supporting Redis/data path is approved;
- phishing URL mismatch checks;
- fuzzy campaign/template matching;
- MIME and attachment-type signals;
- custom multimap rules for local allow/deny/reputation policy;
- rate/reputation scoring;
- additive symbols and explanations that can be carried into the Mail Room audit record.

Rspamd scores are evidence, not a substitute for policy. The Mail Room maps symbols and scores to dispositions using explicit configuration.

## Reputation and blocklist policy

Reputation lookups must be pluggable and terms-aware. No external paid or licensed feed is silently activated.

The initial design reserves provider slots for:

- IP/network reputation such as Spamhaus ZEN-class data;
- low-reputation and compromised domains such as DBL-class data;
- very-new/zero-reputation domains such as ZRD-class data;
- malicious resource/hash intelligence such as HBL-class data;
- Rspamd fuzzy campaign reputation;
- later approved URL, file-hash, sender, or threat-intelligence providers.

Reputation can contribute to reject, spam, or quarantine decisions depending on the signal and confidence. A single weak listing should normally contribute score rather than cause irreversible deletion.

## Phishing and social-engineering detection

The Mail Room must detect and score at least:

- visible-link text that points to a different destination domain;
- lookalike, typosquatted, Unicode/IDN, and brand-impersonating domains;
- newly registered or zero-reputation domains when that signal is available;
- URL shorteners, redirect chains, suspicious tracking/redirector hosts, and encoded destinations;
- credential-harvesting and fake-login language;
- QR-code phishing where QR extraction is safely available;
- fake document-share, e-signature, voicemail, fax, cloud-storage, and password-reset lures;
- executive, employee, vendor, bank, carrier, regulator, and customer impersonation;
- reply-chain/header anomalies and conversation hijacking;
- unexpected payment instructions, bank-detail changes, invoice redirection, payroll diversion, gift-card requests, cryptocurrency requests, and secrecy/urgency pressure;
- requests for passwords, MFA codes, recovery codes, API keys, private keys, or other credentials;
- attachment/content-type mismatch, executable/script payloads, suspicious macros or active content, and malicious archive patterns;
- known malicious URL/domain/IP/file-hash reputation;
- campaign similarity to previously quarantined phishing or spam.

## AI role

AI adds semantic and contextual analysis after hard security preprocessing. It may:

- classify spam, phishing, BEC, fraud, social engineering, routine correspondence, support, or other approved message classes;
- identify unusual requests relative to the apparent sender, thread history, business role, and expected workflow;
- explain why a message appears suspicious using bounded reason codes;
- add risk to the composite score;
- recommend quarantine;
- prepare a safe response when policy allows.

AI must not:

- treat message content as instructions that can change its security policy;
- whitelist a message by itself;
- reduce or override a hard malware/reputation/authentication block;
- release quarantine;
- execute attachments or active content;
- follow links using privileged sessions, cookies, credentials, or the operator's browser identity;
- authorize sending merely because it drafted a response.

Where there is no hard signal, an AI-only high-risk finding should normally require corroboration from at least one non-AI signal before automatic quarantine. An operator may still choose to quarantine based on AI analysis.

## Quarantine classes

Quarantine is appropriate for:

- infected malware;
- suspicious or unscannable required attachments;
- scanner failure where scanning is mandatory;
- high-confidence phishing;
- high-confidence credential harvesting;
- high-confidence malicious URL intelligence;
- high-confidence BEC or impersonation with corroborating evidence;
- payment/bank-change fraud patterns with identity anomalies;
- suspicious conversation hijacking;
- policy combinations whose composite risk crosses the configured quarantine threshold.

Quarantine is not permanent deletion. The operator view must show reason codes, relevant authentication/reputation/security symbols, hashes, scan engines and timestamps, while keeping dangerous active content inert.

Release from quarantine must be an explicit audited action. The AI cannot release mail on its own.

## Automatic replies

The Mail Room may eventually send automatic replies for explicitly allowlisted low-risk classes, for example routine acknowledgements or narrowly defined support/status workflows.

Automatic transmission is disabled by default and must be independently configurable by domain, identity, and message class.

Before any automatic reply is eligible, all of the following must be true:

```text
security disposition clean
+ thread correlation high confidence
+ original recipient preserved
+ sender identity resolved
+ sender live-authorized by the provider
+ domain authentication/alignment valid
+ message class explicitly auto-reply allowlisted
+ not a legal/regulatory/financial/security/credential/contract-sensitive class
+ approved header/footer profile resolved
+ idempotency check passed
+ final outbound malware scan clean
= automatic reply eligible
```

Messages involving complaints, legal notices, regulatory matters, financial instructions, bank changes, credentials/access, security incidents, contracts/terms, termination/cancellation, or other high-consequence matters remain prepare/review workflows unless separately and narrowly authorized.

## Header and footer authority

AI may choose among approved policy profiles, but the server is authoritative for final message construction.

The server must control or validate at least:

- `From` and envelope sender;
- `Reply-To`;
- RFC `Message-ID` generation;
- `In-Reply-To` and `References` preservation;
- WW.CX control/case/action correlation headers;
- mailing-list/commercial preference headers where applicable;
- security and provenance headers appropriate to the provider path;
- approved legal entity, operating name, privacy, confidentiality, commercial, regulatory, accessibility, or role-specific footer text.

The AI must not invent legally material disclaimer wording at send time. Footer/disclaimer text comes from approved versioned configuration and is injected before final DKIM/provider signing.

## Malware depth

The malware layer should evolve beyond a single antivirus lookup. The provider-neutral design should support:

- ClamAV/clamd as the initial local engine;
- YARA rule scanning;
- MIME magic/type verification;
- archive recursion with decompression bombs and resource limits;
- macro/script/active-content detection;
- URL extraction and reputation checks from documents;
- QR-code extraction for URL analysis;
- file-hash reputation;
- optional second antivirus engine;
- optional isolated sandbox/detonation service with strict network and credential isolation;
- local fuzzy/hash memory for previously observed malicious campaigns;
- rescanning when signature/rule sets materially improve before releasing long-lived quarantine.

The AI process never performs first-touch parsing of an unscanned dangerous attachment.

## Disposition philosophy

Use reversible actions wherever practical:

- confirmed protocol-level abuse may be rejected before acceptance when evidence is reliable;
- ordinary spam may go to a spam folder;
- phishing, BEC, suspicious attachments, malware, unscannable required content, or material uncertainty go to quarantine;
- clean mail is delivered to the private or shared Mail Room stream;
- no security engine silently deletes unique correspondence as its normal action.

## Current activation boundary

The repository policy and catch-all routing code can be developed and tested while production mail remains disabled.

Activating live provider ingress, external reputation subscriptions/credentials, DNS/MX changes, live sender identities, or automatic outbound transmission remains a separate controlled production action.
