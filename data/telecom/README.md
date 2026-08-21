# data/telecom/numbering.db

This is the general registry reference database populated by `tools/registry/import_calling_codes.py`,
`tools/registry/import_countries.py`, `tools/registry/import_nanpa.py`, `tools/registry/import_timezones.py`,
`tools/registry/snapshot_registry.py`, and validated by `tools/registry/validate_database.py`. Its tables are
`nanpa_npa`, `carrier_routes`, `registry_metadata`, `country_timezones`, `calling_codes`, and `countries` — the
same reference data also published as JSON under `data/registry/`.

**This is not the WW.CX Numbering Intelligence Node's operational database.** `server/wwcx_numbering_node.py`
(the `wwcx-numbering-node.service`, port 8093) uses its own independent SQLite schema (a single `prefixes`
table, imported via `tools/messaging/../wwcx_numbering_node.py import-csv`, documented in
`docs/telecom/wwcx-numbering-dataset-operations.md`) at the runtime path
`/var/lib/wwcx-numbering-node/numbering.sqlite3` on Edge1 — not this file, and not this schema. The two
share the word "numbering" and both concern NANPA area codes, but they are unrelated systems.
