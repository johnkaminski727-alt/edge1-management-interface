# Mail Room verified state — 2026-08-21

## Authority

This file advances the provider-read portion of `.agent/mail-room-current-state-20260820.md`. Read the 20260820 state for the full local-runtime, provider-inventory, DNS, identity, and adapter history; use this file for the newest provider-access checkpoint.

## Newly verified

The one-time Namecheap Private Email header-only canary is accepted.

At approximately 2026-08-21T02:28Z, GitHub Actions run `32439971393` successfully:

- resolved `mail.privateemail.com`;
- established verified TLS 1.3 to port 993;
- received a valid IMAP greeting;
- verified the secret-backed username matched the exact authorized `blank@ww.cx` SHA-256 binding;
- authenticated successfully;
- selected `INBOX` read-only;
- inspected exactly one newest message header using `BODY.PEEK[HEADER]`;
- emitted only sanitized evidence;
- observed both `Delivered-To` and `X-Original-To` header names on the real provider-delivered message;
- logged out without body fetch, mailbox mutation, Mail Room store write, SMTP, or provider/DNS change.

Canonical acceptance record: `.agent/mail-room-provider-canary-acceptance-20260821.md`.

## Interpretation

Provider selection, reachability, TLS, authentication, read-only mailbox access, bounded UID/header reads, and the existence of original/delivery-recipient metadata on at least one real Namecheap-delivered message are now directly verified.

The earlier statement "live provider login unverified" is obsolete for this bounded header-only scope.

Do **not** generalize the observed delivery headers to every message path. If production ingestion cannot obtain reliable original-recipient evidence for a message, identity-sensitive processing must fail closed.

## Still not activated

The following remain outside the completed canary and require separate authority/design:

- full-message provider-native ingestion using `BODY.PEEK[]`;
- writes to the private `production_native` correspondence store;
- scheduled/persistent Namecheap mailbox polling;
- mailbox-level filter/forwarding inspection or change;
- provider mailbox/alias/forwarder changes;
- outbound SMTP/provider delivery;
- live sender allow-lists;
- automatic replies;
- DNS/MX/SPF/DKIM/DMARC mutation;
- quarantine release/deletion authority.

## Secret posture

Dedicated GitHub Actions repository secrets now exist for the bounded Namecheap canary variable names. Their values are not stored in repository content or evidence.

The temporary secret-consuming one-shot workflow branch was disarmed after successful acceptance and no longer references repository secrets.

Do not copy the secrets into Git, Drive, issues, PR text, logs, or `.agent` files.

## Next decision boundary

There is no remaining engineering blocker to *proving* provider-native read access.

The next functional step would be a separately authorized full-message ingestion acceptance using the already merged `server/mail_namecheap_imap_source.py`, with explicit authority to fetch complete messages and write validated `production_native` correspondence into the private Mail Room store. Persistent polling should remain a later decision unless explicitly included.
