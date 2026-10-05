# AVA intelligence recovery checkpoint — 2026-10-05

Recovered the approved October 5 AVA upgrade scope through conversation search, then inspected live state.

## Live Edge1 changes
- Private Library grew from one bootstrap document to four documents / five chunks, by indexing three existing Library runbooks.
- Search removes conversational stop words, preserves strict matches, broadens partial matches, returns relevant excerpts, and filters secret-bearing rows. Empty conversational queries do not browse records.
- Semantic ranking uses locally stored 512-dimensional text-embedding-3-small vectors, source hashes, collection filtering and a bounded in-memory query cache. Four runbook chunks are indexed; the diagnostic bootstrap is excluded from semantic evidence.
- Semantic-only retrieval for "Making a restorable copy of my knowledge store" ranked the backup runbook first.
- The existing loopback gateway supports explicit include_web + web_query with web:search scope. Public research receives only that query, not the private assembled context. Hosted web_search returns bounded cited sources.
- Browser-agent routing accepts the original routing_message. Source scopes remain server-authorized and can only be narrowed.
- The Library API now preserves source locators/classification.

## Verification
Signed Library/model acceptance passed, including unsigned-request and replay rejection.
An actual signed web query returned HTTP 200, a model-backed answer and Python/SQLite citations.
Gateway, Library search and browser worker services were active after deployment.
Regression tests cover retrieval bounds, secrets, collections, query excerpts, semantic staleness, provider fallback, web scope checks, public-query isolation and controller narrowing.

## Website candidate
https://github.com/johnkaminski727-alt/ww-cx-website/pull/152
Commit: 315d6a9a754866d288bc857e75601bf0d4a74ef9
Includes project memory isolation, relevant durable records, provenance/confidence, editing, expiry and locking; public research controls, clickable retained citations and OAuth-aware Airtable status.
PHP/JS syntax, browser-interface validation, memory tests (including concurrent writes), and credential-status tests passed.
Not deployed to Business159. Its SSH alias/credentials are not available from this session.

## Recovery
Preservation directory: /home/wwadmin/edge1-preservation/ava-library-upgrade-20261005T033919Z
Contains initial source/runtime files, a consistent pre-import SQLite copy and the import manifest.
A concurrent Library recall update was preserved and reconciled with the secret/empty-query guards.
Restore saved source/runtime files and the SQLite backup only through an attended rollback while stopping the affected Library/gateway readers; then restart and repeat signed acceptance. Do not overwrite unrelated security or Contacts work.

## Sources
https://developers.openai.com/api/docs/guides/tools-web-search
https://developers.openai.com/api/docs/guides/embeddings
