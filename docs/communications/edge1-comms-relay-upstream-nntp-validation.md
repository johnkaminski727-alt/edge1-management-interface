# Edge1 Upstream NNTP Validation Plan

Last reconciled: 2026-08-17

## Purpose

This plan is the acceptance standard for selective outbound NNTP reader sources on the private Edge1 Communications Relay. It incorporates the production lessons from the accepted `comp.lang.python` and `news.admin.peering` activations.

## Repository gate

Before merging changes to the NNTP ingestion implementation or News Reader:

- run the relevant scripted protocol/reader validation;
- run Communications Relay production-readiness validation;
- run controlled-ingestion regression validation;
- run config-control metadata validation when configuration control is touched;
- validate JavaScript syntax when News Reader assets change;
- require a clean, scoped diff and mergeable PR;
- confirm no credentials, live database copies, or unredacted evidence are committed.

Repository merge alone never activates an external source.

## Config-only live activation gate

When adding one new allowlisted reader mapping, proceed in this order:

1. freeze and record the clean local Edge1 checkout;
2. verify relay service, listeners and health;
3. verify config/credential metadata without displaying credential contents;
4. back up `/etc/wwcx/comms-relay.json` and the relay SQLite database;
5. create exactly one reviewed NNTP mapping in a candidate config;
6. validate and diff the candidate;
7. run an attended `ingest run --dry-run` against the candidate over real TLS;
8. inspect candidate count, target group, source Message-IDs, article numbers/content type and size bounds;
9. prove the dry run did not mutate group, article, cursor, or ingest state;
10. stage/apply the candidate and restart only `edge1-comms-relay.service`;
11. wait for bounded `/healthz` and listener readiness;
12. verify live config metadata and exact source mapping;
13. run attended ingestion, retrying later if the ingestion lock reports `already_running`;
14. perform a second ingestion pass when needed so `wwcx-bootstrap` can create the one-time introduction for a newly created group;
15. validate external provenance, duplicate identity, target group, cursor, bootstrap introduction and error counts;
16. re-run relay health and loopback listener checks;
17. preserve sanitized evidence and update acceptance/state records.

## Service-readiness requirement

`edge1-comms-relay.service` uses systemd `Type=simple`. `systemctl is-active` is process state, not application readiness.

After a restart, use a bounded retry loop against `http://127.0.0.1:8100/healthz` and confirm listeners. A one-shot immediate curl can fail while the process is still initializing.

The accepted second-source operation demonstrated this race, exercised rollback successfully, then completed with bounded readiness.

## Rollback rule

If post-apply runtime verification fails before accepted ingestion:

- restore the previous relay configuration through config-control rollback;
- restart only the relay;
- wait for bounded health/listener readiness;
- preserve the failed-attempt evidence;
- prove whether any candidate-era database mutation occurred.

Do not delete imported articles as an automatic rollback action. If data was created before a later validation failure, preserve it and inspect before any cleanup. Deletion requires separate review/authorization.

## Provenance-aware article accounting

Never validate an imported local group by assuming all its articles came from the external source.

`wwcx-bootstrap` can legitimately create a one-time introduction after an imported group appears.

Classify articles by ingestion provenance:

- external: exact configured `source_name`, unique upstream `source_item_id`, correct target group;
- bootstrap: `source_name=wwcx-bootstrap`, source item ID `<group>:v1`;
- any other provenance class must be explicitly understood before acceptance.

Accepted examples:

### `usenet.comp.lang.python`

- 8 `eternal.comp.lang.python` items;
- 1 `wwcx-bootstrap` introduction (`usenet.comp.lang.python:v1`);
- 0 duplicate external source IDs.

### `usenet.news.admin.peering`

- 8 `eternal.news.admin.peering` items;
- 1 `wwcx-bootstrap` introduction (`usenet.news.admin.peering:v1`);
- cursor present;
- 0 duplicate external source IDs;
- 0 wrong-group items;
- 0 orphan items;
- 0 bad-provenance items;
- 0 unexpected-provenance items;
- 0 ingestion errors since activation at the acceptance checkpoint.

Therefore raw group count equality is not a valid invariant. Validate the source ledger and explicit provenance classes.

## Repository movement during attended activation

Do not chase a rapidly advancing remote `main` during a config-only activation when unrelated workstreams are merging.

Instead:

1. freeze the local checkout revision at the start;
2. require the validated implementation floor to be an ancestor;
3. inspect protected relay paths for unexpected changes;
4. stop if the local implementation is not the tested one;
5. otherwise complete the bounded operation on that frozen checkout;
6. record production checkout and later documentation/repository merge state separately.

The accepted News Reader deployment remains on `deploy/private-nntp-news-reader-v2-20260817` at `974c7141e18deac92671f81fb1bd3c3ed02a6c68`; repository reconciliation through PR #341 does not authorize changing that production checkout.

## News Reader validation gate

For private News Reader changes, verify at minimum:

- group listing and article counts;
- bounded pagination and previous/next offsets;
- article-list responses exclude bodies;
- exact source filtering, including native/local;
- combined search + source filtering;
- thread ancestry from stored references;
- article detail body and provenance;
- source endpoint readability;
- HTTP mutation attempts return 405 `read_only_control_api`;
- JavaScript parses successfully;
- relay health/listeners remain accepted after restart.

## Archive validation gate

Before the Communications Relay closeout is marked sealed:

- resolve the exact News Reader v2 protected evidence path;
- enumerate every file under the retained evidence roots;
- record SHA-256 plus path/size/mode/owner/group/mtime;
- hash live config and SQLite without committing them;
- exclude credential contents;
- reconcile retained, unavailable, duplicate and error totals;
- rerun the inventory and require idempotent totals;
- merge the final sanitized archive-manifest update.

See `../archive/edge1-comms-relay-news-reader-closeout-20260817.md`.

## Deferred / forbidden-by-default gates

The following are not authorized by successful reader activation:

- peering requests;
- inbound NNTP feed acceptance;
- server-to-server streaming;
- upstream posting;
- DNS or firewall changes;
- public Edge1 IRC/NNTP exposure;
- forwarding WW.CX articles upstream;
- credential disclosure;
- deletion of retained deployment evidence.
