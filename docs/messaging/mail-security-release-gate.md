# Edge1 incoming mail security gate

All inbound correspondence needs a released decision before the signed gateway can
return its body, include it in a thread, or discover it for AVA. Inbox, unread,
archive and all-mail views enforce the same rule. Missing decisions or an unavailable
security database fail closed. Writable transport stores retain private originals;
transport provenance does not imply sender authentication or a clean security result.

The private worker inspects each complete RFC822 message and decoded leaf attachments,
including inline binary parts, with ClamAV. Stale daily signatures, scanner errors,
timeouts and inspection limits cannot produce a clean result. Executables, scripts,
macro-enabled document extensions and detected executable signatures are blocked.
Rspamd supplies content, phishing, reputation, DKIM and DMARC signals. Direct SMTP
SPF uses client IP and envelope sender recorded out of band by the Postfix pipe.
Received and Authentication-Results headers are not transport evidence. Provider
imports disable SPF rather than guessing a connection IP; their DKIM can still be
validated. Trusted provider authentication header acceptance needs a separately
verified provider boundary and is not enabled merely by an authserv-id string.

Messages are released, junk, quarantine or pending. Unknown catch-all recipients
are retained for review even when scans pass. No permanent sender/domain block,
automatic deletion, attachment download, external message submission or public
SMTP activation is added. Rspamd URL reputation queries do not entail visiting
message links. Fuzzy cloud queries, GPT content analysis and URL redirect fetching
are disabled. Provider-side inbox filtering remains a separate commissioning step.

## Operator workflow

- Spam / Not spam correct classification and queue local Bayes learning. Learning
  needs sufficient examples before it contributes to decisions.
- Report phishing quarantines immediately and records whether the operator interacted
  with a link or file. Reports and confirmations remain distinct.
- Exact sender, link and attachment-hash matches are held for related-message review;
  this creates no permanent blacklist. Broad shared hosting domains are not matched.
- Quarantine review requires an explicit acknowledgement before displaying plain text.
  It does not call AVA, enable active HTML, follow URLs or provide attachment bytes.
- Reviewed release requires completed checks and no hard file/integrity finding.
  Confirmed phishing cannot be released using the ordinary controls. Not spam cannot
  release quarantine. An operator override cannot make unscanned mail safe.
- Per-domain thresholds and exact trusted sender addresses are configurable. Trusted
  senders receive a small scoring adjustment only with aligned DMARC and passing DKIM;
  phishing and attachment checks remain authoritative.

Daily reports contain aggregate classification transitions, phishing reports,
confirmations, corrections, related holds and releases. Rescans can produce another
transition; these are not unique-message totals. Private originals and security
state remain on Edge1. AVA receives no quarantine management or release capability.

## Deployment and validation

Install Debian Rspamd and Redis packages, stage an immutable approved git release,
then run `deploy/messaging/install-mail-security.py --release /opt/wwcx-email/releases/SHA`
on Edge1. The installer backs up SQLite state and affected configuration, keeps all
workers on loopback, applies resource limits, enables the shared read gate, and
replaces advisory attachment scanning with `wwcx-mail-security-scan.timer`.
Existing portal authentication, private routing and disabled outbound delivery remain.

Regression coverage verifies search, direct message and mixed-thread exclusion,
inbox folders, missing-store failures, reports surviving rescans, related holds,
release restrictions, attachment rules, spoofed authentication headers, trusted
transport input and per-domain settings. Commissioning still requires actual
provider credentials, a trusted incoming SMTP connection and end-to-end real-domain
SPF/DKIM/DMARC canaries. A domain-authenticated label never verifies a person or
promises that a compromised legitimate account is harmless.
