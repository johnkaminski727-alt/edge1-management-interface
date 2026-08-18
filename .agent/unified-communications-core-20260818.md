# Unified Communications core — 2026-08-18

Repository: `johnkaminski727-alt/edge1-management-interface`
Branch: `agent/unified-communications-core-20260818`
Base: `73b83c4685e7d9c9cda1f53bea1f96602c24dc77`

## Objective

Create the safe channel-neutral contract layer required before adding cross-channel AI adapters and a real Communications inbox/timeline.

## Implemented on this branch

- canonical `wwcx.communications-event.v1` metadata contract;
- evidence-only `wwcx.communications-identity-registry.v1` facade;
- machine-readable `wwcx.communications-readiness.v1` matrix;
- pure metadata validation, deterministic ordering, search, conversation correlation, explicit identity-link resolution, and untrusted-derived-metadata sanitization;
- focused failure-path tests;
- architecture/security documentation.

## Safety state

No provider/network/runtime mutation is implemented by the core library.

The unified layer cannot authorize quarantine release. Raw message bodies, raw audio, attachment bytes, credentials, passwords, private keys, secrets and tokens are rejected from canonical events. Search is limited to an explicit metadata allowlist. Identity correlation requires evidence references. Retrieved data cannot grant scopes, permissions or tool authority.

Repository readiness is kept distinct from Edge1 runtime readiness and production authorization.

## Validation state

Focused tests are present in `tests/test_unified_communications_core.py`. Branch CI is the acceptance gate before merge. Fresh Edge1 live validation is not claimed by this repository-only increment.

## Next safe increments after merge

1. bounded SMS/MMS AI status/conversation read adapter with PostgreSQL read parity;
2. Mail Room AI status and `prepared_not_sent` draft adapter without send authority;
3. unified conversation/search API over canonical metadata references;
4. Communications inbox/timeline/readiness UI;
5. final archive/handoff reconciliation and fresh read-only Edge1 verification when the approved connector is available.

## Privileged boundaries unchanged

Do not enable live SMS/MMS, originate calls, change SIP/carrier/emergency routing, enable live mail transmission, release quarantine, alter credentials, DNS, firewall, certificates or authentication policy, or perform destructive changes without separate explicit authorization.
