# Unified Communications — Validation Record

Date: 2026-08-18
Scope: repository-side completion and CI evidence
Fresh authenticated Edge1 host acceptance: not performed in this execution environment

## Accepted merged increments

| PR | Increment | Final head / merge evidence | CI result |
|---|---|---|---|
| #384 | Canonical event / identity / readiness / correlation core | merge `6b272fb0308bfeb161f50598845fc88b77e5c561` | Validate repository PASS; Edge1 Operator Validation PASS |
| #385 | SMS/MMS Private AI read + draft | merge `ce5c561304a0a7aa109b887d1739ae90660b7633` | Messaging Gateway PASS; BigBird Messaging Adapter PASS; Validate repository PASS; Edge1 Operator Validation PASS |
| #386 | Mail Room AI status + draft | merge `9e26ea6df6e0bc3469d3bc63701362b01a80bd94` | Validate repository PASS; Edge1 Operator Validation PASS |
| #387 | Unified Communications workspace | merge `2b4550812cb6bc790cb3b3bc0d079bdfd261b220` | Validate repository PASS; Edge1 Operator Validation PASS |
| #389 | MMS media quarantine foundation | merge `721d5e538835a4b53a05c2208e7940f1d83ec043` | Messaging Gateway PASS; Validate repository PASS; Edge1 Operator Validation PASS |

## Contract validations

Repository validation now covers or is backed by focused tests for:

- canonical event validation and authoritative native-record provenance;
- rejection of embedded raw message/private/credential fields from the canonical layer;
- deterministic conversation ordering;
- metadata-only search allowlist;
- explicit-evidence identity links and rejection of name-similarity inference;
- retrieved/untrusted metadata inability to grant scopes or tool authority;
- quarantine release fail-closed behavior;
- SMS/MMS read-token enforcement and sanitized media projection;
- SMS/MMS draft != send;
- Mail draft != send and no network activity;
- provider/source failure-safe boundaries;
- loopback-only workspace binding and rejection of mutation verbs;
- JavaScript syntax and responsive workspace assets;
- MMS pending-scan, missing-digest, malicious, scan-error, and clean-held states;
- SMS quarantine not-applicable semantics where no media exists.

## Evidence interpretation

`Edge1 Operator Validation` is a repository CI workflow name. A green CI result is retained as CI evidence only and must not be represented as a fresh authenticated inspection of the live `edge1.ww.cx` host.

The readiness matrix therefore keeps `fresh_edge1_runtime_verified: false` and does not convert historical subsystem acceptance into a current deployment assertion.

## Fresh live acceptance still required

When the approved Edge1 Live Shell connector is available, perform a read-only acceptance pass that records:

1. live repository/release revision and working-tree state;
2. relevant loopback listeners and service status;
3. Private AI gateway version and accepted scopes without exposing credentials;
4. Messaging Gateway version/read endpoints and quarantine state;
5. Communications workspace listener, canonical snapshot source, and browser route;
6. Mail Room adapter availability and prepare-only semantics;
7. Voice/SIP and Relay read-only capability health;
8. rollback/checkpoint evidence for any already-deployed runtime component.

Do not use production calls, messages, or email as acceptance tests.
