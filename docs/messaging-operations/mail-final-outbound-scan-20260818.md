# Mail Room final outbound scan boundary — 2026-08-18

## Scope

This increment makes the final outbound security boundary explicit and fail-closed without activating any provider, scanner runtime, mailbox, DNS record, or production mail path.

`server/mail_final_scan.py` defines normalized final-scan evidence. `server/mail_secure_submission.py` accepts an already policy-composed preview, builds the provider-bound MIME message once, serializes it once, requires a clean scan result tied to the SHA-256 of those exact bytes, and only then permits provider submission.

Normalized states are:

- `clean`;
- `infected`;
- `suspicious`;
- `unscannable`;
- `scan_error`;
- `not_scanned`.

Only `clean` permits the secure submission boundary to proceed. Missing scanners, malformed results, mismatched message digests, and every non-clean state fail closed.

## Composition ordering

The authoritative ordering is:

1. resolve the server-authoritative sender identity;
2. compose policy-controlled headers, body, footer/disclaimer and control metadata;
3. apply validated correspondence/thread headers;
4. construct the final MIME message, including Date and Message-ID;
5. serialize the exact provider-bound MIME bytes;
6. scan those exact bytes;
7. require normalized `clean` with a matching SHA-256;
8. submit those same bytes to the provider adapter;
9. retain bounded scan provenance in the delivery audit event.

The scanner therefore sees the content after policy/footer/thread composition and before provider submission. The provider adapter does not receive a separately rebuilt message after scanning.

## Threading regression fixed

Before this increment, the identity-aware preview applied `X-WWCX-Correspondence-ID`, `X-WWCX-Thread-ID`, `In-Reply-To`, and `References`, but the identity-aware send path recomposed the payload through the lower gateway. That could drop the reviewed thread metadata on the send path.

The identity-aware send path now submits the already composed identity/thread-aware preview through the secure submission boundary. Focused tests prove the explicit threading headers arrive at that boundary.

## Audit minimization

Final-scan audit metadata is bounded to the normalized state, engine/ruleset identifiers and versions, reason codes, contract, and SHA-256 of the final MIME bytes. The final MIME body, raw malicious payloads, credentials, and scanner secrets are not added to the general delivery audit event.

## Activation boundary

The HTTP gateway does not install or supply a final scanner callback. Therefore the committed system remains unable to send through this secure path even if other send gates were hypothetically enabled until an approved server-side scanner adapter is deliberately installed and connected.

No production mail was transmitted. No scanner daemon or external service was installed. No provider credentials, MX, SPF, DKIM, DMARC, DNS, firewall, certificate, mailbox, or production routing state was changed.
