# Messaging carrier readiness contract — 2026-08-23

## Purpose

Prepare the Telnyx and Bandwidth adapters for an eventual controlled activation without registering either carrier, reading or printing secret values, contacting a provider, assigning a DID, exposing a webhook, or authorizing live SMS/MMS traffic.

The active runtime provider registry remains simulator-only.

## Secret-free configuration presence contract

`app/provider_readiness.py` defines the names of configuration values that a future private runtime would need. The readiness function reports only whether each required name is present and non-empty. It never returns the value, its length, a hash, a prefix, or any other derivative of the secret.

### Telnyx

Inbound callback authentication readiness requires:

- `WWCX_TELNYX_WEBHOOK_PUBLIC_KEY`

Outbound submission readiness requires:

- `WWCX_TELNYX_API_KEY`

Authenticated MMS acquisition also requires the API key because the existing Telnyx adapter retrieves allowlisted Telnyx media directly into the private quarantine store.

### Bandwidth

Inbound callback authentication readiness requires:

- `WWCX_BANDWIDTH_WEBHOOK_USERNAME`
- `WWCX_BANDWIDTH_WEBHOOK_PASSWORD`

Outbound Messaging-V2 readiness requires:

- `WWCX_BANDWIDTH_ACCOUNT_ID`
- `WWCX_BANDWIDTH_API_USERNAME`
- `WWCX_BANDWIDTH_API_PASSWORD`
- `WWCX_BANDWIDTH_APPLICATION_ID`

Bandwidth MMS acquisition is **not** marked ready merely because credentials are present. The current adapter validates allowlisted media references but does not yet implement the authenticated, digest-establishing acquisition path required by the private quarantine boundary. The readiness result therefore exposes the fixed blocker `BANDWIDTH_MMS_ACQUISITION_NOT_IMPLEMENTED`.

## Gates that configuration cannot satisfy

The following remain false regardless of configuration presence:

- public webhook ready;
- sender/DID binding verified;
- live traffic authorized.

Those states require separate provider, infrastructure and operator evidence. This contract intentionally has no environment variable that can flip those gates true.

## Runtime CLI

`scripts/provider-readiness.py` emits the sanitized contract against the process environment and compares it with the active provider registry. It is safe to run in a credential-bearing service environment because it outputs field names/booleans only.

The CLI must continue to show only `simulator` in `active_provider_names` until an independently reviewed activation change is approved.

## PBX + Messaging runtime capture

`tools/communications/capture-pbx-messaging-runtime.sh` captures the remaining live deployment facts needed for repository reconciliation:

- Asterisk version and aggregate call/PJSIP counts only;
- Messaging service active/unit metadata;
- a SHA-256 of the actual service unit fragment;
- a redacted copy of the unit definition;
- loopback health/readiness responses;
- quarantine-root metadata only, never its contents;
- ClamAV version only;
- relevant listener addresses/ports.

Inline `Environment=` values are always removed. Sensitive-looking `ExecStart` options/assignments are redacted. The audit does not enumerate message/quarantine content or retain telephone numbers, SIP URIs, endpoint names, credentials, provider payloads, media, or call records.

## Remaining activation boundary

Even a fully configured readiness report does not authorize:

- provider account/contract acceptance or charges;
- credential creation/rotation;
- DID/number purchase or assignment;
- public webhook DNS/firewall/certificate/reverse-proxy changes;
- live inbound or outbound SMS/MMS canaries;
- production traffic cutover;
- quarantine release;
- legal/regulatory representations.

The next safe operator step after merge is to run the read-only runtime capture and sanitized provider-readiness CLI on Edge1. Any provider registration or live traffic remains a separate explicit gate.
