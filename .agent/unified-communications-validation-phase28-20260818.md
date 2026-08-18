# Unified Communications — Phase 28 Validation Record

Date: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Implementation PR: #427
Implementation branch base: `9711461125a73f013b0f0a09347a6b1d1105eb5f`
Reviewed exact head: `88253f0c3c2839b2192cc1d9f723c92a79b293be`
Merge SHA: `e7d7fda638a4f69d68bf54cdebdbee9070143384`

## Result

Phase 28 delivered a functional **local-native** Mail correspondence software path and merged it to `main` without claiming provider-production or live Edge1 acceptance.

Functional chain validated in CI:

`generated local RFC822 -> bounded native parser -> private SQLite correspondence store -> authenticated loopback Mail API -> BigBird Mail facade -> mail.correspondence.read`

Draft preparation also remained `prepared_not_sent` with live delivery disabled.

## Exact-head CI

All required checks passed on `88253f0c3c2839b2192cc1d9f723c92a79b293be` before merge:

- Validate repository — run `32196436559` — PASS;
- Edge1 Operator Validation — run `32196436531` — PASS;
- Validate outbound mail suppression server — run `32196436670` — PASS.

An earlier exact-head repository run on `122cd02798b4f499df8a0ba82f29d941a90f25ee` also passed the full end-to-end functional Mail test before the final client-isolation hardening. The final head reran and passed the complete validator after that hardening.

## Functional Mail acceptance covered by repository validation

`tests/validate_mail_correspondence_functional.py` passed and exercised:

- correspondence disabled by default;
- local RFC822 root message ingest;
- local RFC822 reply ingest;
- canonical Message-ID persistence;
- explicit In-Reply-To / References thread reconstruction;
- optional native/provider message and thread ID preservation;
- `text/plain` persistence with HTML-only input rejected;
- `0700` private parent and `0600` database permissions in the local fixture;
- immutable `local_native` authoritative provenance;
- synthetic record isolation;
- direct Mail AI individual-message and thread reads;
- local-native readiness explicitly marked `production_provider_ready=false`;
- unsigned API correspondence access rejected;
- authenticated correspondence status/message/thread reads;
- BigBird Mail facade correspondence reads;
- prompt-like message text retained as untrusted data with no tool/scope authority;
- prepared-not-sent draft path with live delivery authorization false;
- production HMAC allowed-client policy left unchanged in repository configuration.

## Security review findings fixed before merge

### Immutable provenance

Phase 27 had already fixed a provenance defect where reopening a synthetic database with a differently configured reader could have relabeled records. Phase 28 extended that defense with persisted source scopes:

- `synthetic`;
- `local_native`;
- `production_native`;
- `legacy_unscoped` fail-safe scope.

Only persisted `authoritative=true` records in `local_native` or `production_native` scope are readable through `mail.correspondence.read`.

### Existing-client privilege inheritance

Manual Phase 28 review found that simply placing correspondence endpoints behind the existing HMAC API could have let the already-authorized `wwcx-website-admin` client inherit message-body read authority.

Fixed before merge:

- correspondence endpoints require a valid HMAC **and** exact client ID `wwcx-private-ai`;
- existing website-admin and unrelated clients fail the correspondence-client gate;
- `tests/validate_mail_correspondence_client_isolation.py` covers the regression;
- base/deployed allowed-client policy was not changed by PR #427.

### Filesystem/projection boundary

- runtime correspondence database configuration is constrained to the private Mail Room root `/var/lib/wwcx-mail-room`;
- API status reports a logical private-store label rather than exposing the database path;
- Private AI cannot provide a filesystem path to correspondence endpoints;
- correspondence store read mode uses SQLite `mode=ro` and rejects writes;
- local intake is a separate operator path, not an API write endpoint.

## Repository capability truth

Repository-ready:

- `mail.status.read`;
- `mail.draft.prepare`;
- `mail.correspondence.read` for explicit local-native/production-native persisted records.

Accepted live capabilities remain unchanged from prior Edge1 evidence. `mail.correspondence.read` is **not** added to the accepted-live set because Phase 28 had no authenticated Edge1 execution path.

Provider-production correspondence remains separately unproven. Local-native records are never represented as provider-native.

## Edge1 execution blocker

This session did not expose the Edge1 Live Shell connector or another authenticated Edge1 execution connector. The available execution container had no usable SSH identity/path.

Therefore Phase 28 did **not** claim:

- live creation/permission verification of `/var/lib/wwcx-mail-room`;
- live local RFC822 intake on Edge1;
- live correspondence-read activation;
- live `wwcx-private-ai` HMAC client registration;
- live BigBird Mail-tool registration;
- live Mail service restart/recovery acceptance;
- live MMS ClamAV/private-root acceptance.

This is an execution-path limitation, not a repository software failure.

## Explicit authentication-policy boundary

Registering `wwcx-private-ai` in the deployed Mail gateway HMAC allowed-client set is an authentication-policy change. The task instructions explicitly reserve authentication-policy changes for separate approval, so PR #427 deliberately left the base/deployed allowed-client policy unchanged.

Do not reuse or impersonate the website-admin identity merely to bypass this boundary.

## MMS state

The Phase 27 repository MMS implementation remains intact:

- private content-addressed quarantine store;
- fail-closed quarantine states;
- fixed local `/usr/bin/clamscan` adapter;
- local clean/EICAR/failure/restart acceptance tooling;
- no automatic release.

Live Edge1 scanner/private-root acceptance remains pending because no authenticated host execution path was exposed.

## Final interpretation

Phase 28 satisfies the required fallback software outcome when provider-native correspondence cannot be connected: the complete local-native Mail path is implemented, test-executed, security-reviewed, CI-green and merged.

It does **not** convert local repository/CI evidence into live Edge1 evidence, provider readiness, production send authority, authentication-policy approval, or quarantine-release authority.

`fresh_edge1_runtime_verified` remains `false`.
