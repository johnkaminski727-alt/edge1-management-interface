# WW.CX Unified Communications core contracts

Date: 2026-08-18

## Purpose

This increment creates the channel-neutral metadata foundation for WW.CX Communications without replacing Mail Room, Messaging Gateway, Voice/SIP, Communications Relay, or Private AI native records and without adding production mutation authority.

## Canonical event contract

`config/communications/communications-event-v1.json` defines `wwcx.communications-event.v1`.

The contract carries identifiers, channel, direction, UTC timestamp, identity references, native/provider record references, bounded subject/summary metadata, common action state, security state, media hashes/metadata, correspondence relationships, derived/AI metadata, provenance, and audit references.

The native record remains authoritative. The unified event is a correlation record, not a second message store. Raw message bodies, audio, attachment bytes, passwords, credentials, private keys, secrets, and tokens are outside this layer.

Common lifecycle states are:

`observed`, `summarized`, `drafted`, `reviewed`, `approved`, `queued`, `submitted`, `delivered`, `failed`, `suppressed`, `quarantined`, `closed`.

Channel-native states may still exist in the authoritative channel service.

## Identity registry

`config/communications/identity-registry-v1.json` establishes an evidence-only channel-neutral registry facade.

It can represent email/catch-all/domain, phone/SMS, SIP, Relay, internal user/role, organization/contact, case, and project identities. Empty `records` and `links` are intentional until authoritative evidence is supplied.

Identity correlation is explicit. Similar names are not evidence, cross-channel inference is disabled, links require evidence references and provenance, and ambiguous records remain unlinked.

## Search and correlation core

`server/unified_communications.py` is a pure metadata library. It performs no network, provider, filesystem, mail-delivery, telephony, SMS/MMS, Relay, or configuration mutation.

It provides:

- fail-closed event validation;
- deterministic chronological ordering with event-ID tie breaking;
- search over an explicit metadata allowlist only;
- conversation correlation by explicit ID;
- identity-link resolution only when evidence references exist;
- derived-metadata sanitization that drops scope/permission/tool-authority claims from retrieved untrusted material.

The library rejects embedded raw/private fields and refuses to let the unified layer authorize quarantine release.

## Readiness matrix

`config/communications/readiness-matrix-v1.json` separates repository implementation, CI, Edge1 runtime, Private AI adapter, identity mapping, security/quarantine, provider configuration, credentials, DNS/authentication, live routing, production authorization, live acceptance, and rollback evidence.

The matrix deliberately records unknowns rather than converting historical evidence into a fresh runtime assertion. Its rules make these distinctions explicit:

- repository ready does not mean runtime ready;
- runtime ready does not mean live authorized;
- unknown credential state does not mean credentials are absent;
- historical acceptance does not mean fresh runtime acceptance.

## Security boundary

This increment does not send email, SMS/MMS, originate a call, mutate a SIP route, release quarantine, change carrier/provider routing, modify DNS/firewall/certificates/authentication policy, inspect or create credentials, or expose generic execution through AI.

Read remains distinct from write. Draft remains distinct from send. Retrieved communications remain untrusted data and cannot grant tool scopes.

## Validation

Focused tests live in `tests/test_unified_communications_core.py` and cover native-record authority, forbidden raw/private content, quarantine fail-closed behavior, deterministic ordering, metadata-only search, evidence-only identity links, untrusted-content scope stripping, immutable input behavior, and provenance/channel consistency.

Repository CI remains separate from live Edge1 acceptance.
