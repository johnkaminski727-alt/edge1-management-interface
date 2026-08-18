# Mail Room thread correlation foundation — 2026-08-18

## Scope

This increment adds validated, provider-neutral correlation metadata to outbound **preparation**. It does not activate sending or infer thread relationships from untrusted message content.

Supported explicit evidence:

- WW.CX `correspondence_id`;
- WW.CX `thread_id`;
- source RFC `Message-ID`;
- `In-Reply-To`;
- `References` chain;
- provider thread/conversation ID;
- provider message ID;
- existing WW.CX case/control/action identifiers remain unchanged.

## Rules

`server/mail_threading.py` normalizes this evidence and rejects CR/LF injection, malformed RFC-style Message-ID values, excessive reference chains, and malformed WW.CX identifiers.

When a source Message-ID is supplied and `in_reply_to` is absent, the source Message-ID becomes the explicit reply parent. The parent is appended to `References` when needed.

No subject-line, sender-name, or semantic fallback matching is performed. `fallback_correlation_used` remains false. Bounded fallback correlation can be added later only with explicit ambiguity controls.

## Prepared headers

Explicit safe correlation may add:

- `X-WWCX-Correspondence-ID`;
- `X-WWCX-Thread-ID`;
- `In-Reply-To`;
- `References`.

Opaque provider IDs remain internal metadata and are not emitted as public email headers.

## Production boundary

This is a no-send preparation foundation. Live provider submission remains disabled by the existing gateway, sender authorization, provider, and policy gates. No DNS, provider, credential, routing, or legal-text state is changed.
