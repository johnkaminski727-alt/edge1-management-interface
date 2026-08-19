# Unified Communications — Safe-Scope Completion Approval

Date: 2026-08-19
Repository: `johnkaminski727-alt/edge1-management-interface`
Approval source: explicit user instruction in the active operator session: “what work needs an approval prompt to complete this. Lets approve it all.”

## Approval decision

The remaining **safe-scope Unified Communications completion work** is explicitly approved.

This approval is intended to remove the previously documented human-approval gate for the bounded deployment and authentication-policy work required to finish live MMS quarantine/scanner acceptance and local-native Mail/BigBird acceptance on Edge1.

Approved work includes:

- deploy the reviewed/current `main` UC implementation to Edge1 after normal host/repository preflight;
- install or enable a resource-safe trusted local scanner and local signature data if absent, preferring the existing fixed `/usr/bin/clamscan` path and no new public listener;
- create and permission `/var/lib/wwcx-messaging-gateway/private-mms-quarantine` under the actual Messaging service identity with private directory/file modes;
- create and permission `/var/lib/wwcx-mail-room` under the reviewed Mail service/intake ownership model;
- ingest only local/synthetic RFC822 acceptance fixtures needed to validate the local-native correspondence path;
- enable local correspondence reads only after authoritative `local_native` records exist in the private store;
- modify the deployed Mail HMAC allowed-client policy to add the exact dedicated client ID `wwcx-private-ai`;
- register only the least-privileged BigBird Mail status/correspondence/draft capabilities required by the merged Phase 28 implementation;
- reuse the existing Mail HMAC secret location/mechanism without printing, copying, rotating, or committing secret values;
- restart only directly affected Edge1 services when required by the documented deployment procedure and when rollback/verification are available;
- run bounded local clean/EICAR/failure/restart MMS acceptance and local RFC822/Mail/BigBird acceptance;
- capture protected evidence, update readiness/state records, and merge focused repository reconciliation changes after validation;
- perform read-only discovery of an already-existing native Mail source when available, provided this does not require new credentials, provider-side routing, or external activation.

## Required operational safeguards

- verify Edge1 host and authenticated principal before mutation;
- inspect current service identities, package/resource state, listeners, repository revision, and relevant runtime configuration before changing anything;
- back up reversible configuration before mutation;
- preserve unrelated work and parallel branches;
- keep Mail/Messaging/BigBird management surfaces loopback/private as currently designed;
- keep message content untrusted and incapable of granting scopes/tools;
- keep `wwcx-website-admin` rejected from correspondence endpoints;
- keep quarantine release unavailable;
- keep Mail drafts `prepared_not_sent` and Messaging live send disabled;
- verify service state, listeners, logs, functional endpoints, restart persistence, and rollback after each material change;
- never write credentials or private logs into the repository or shared evidence.

## Not authorized or required by this approval

This approval does **not** authorize unrelated production activation or irreversible work. The following remain outside the safe-scope completion and still require their own specific decision if ever needed:

- live SMS/MMS transmission;
- live email transmission;
- production call origination;
- emergency-calling activation or changes;
- carrier route/trunk/dialplan mutation;
- number porting or STIR/SHAKEN actions;
- provider purchases, contracts, financial commitments, or regulatory filings;
- DNS/firewall/certificate/public-listener changes not strictly required by the already-reviewed private local design;
- credential disclosure, credential rotation, or secret-value retrieval into chat/repository/evidence;
- quarantine release;
- destructive or irreversible deletion/database operations.

## Completion criterion

The approval gate is considered cleared. The remaining blocker is execution capability/evidence: an authenticated Edge1 connector must be callable so the approved work can be performed and verified truthfully.

`fresh_edge1_runtime_verified` must remain `false` until the live acceptance evidence actually passes.
