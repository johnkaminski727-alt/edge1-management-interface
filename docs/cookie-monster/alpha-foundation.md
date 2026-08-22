# Cookie Monster Alpha Foundation

Status: source implementation foundation, read-only Alpha boundary.

## Product rule

Cookie Monster is not complete as a headless service. Every material capability must have a human-facing control surface. The Alpha UI lives at `src/web/cookie-monster/` and uses the project mascot as a primary visual element.

## Authority split

- **Big Bird**: orchestration/control plane.
- **Cookie Monster**: ingestion, normalization, extraction, analysis, knowledge synthesis, provenance and review visibility.
- **Fengus**: future bounded execution worker. It receives work items and returns results; it does not receive direct archive credentials or authority.
- **Human operator**: owns approval decisions. Alpha surfaces review items but does not silently invent an approval mutation path.

## Alpha source boundary

`server/cookie_monster_alpha.py` accepts a staging source directory and a separate generated-output directory. The output may not be the source directory or a descendant of it. The source is read only. Symlink files and symlink directories inside the staging source are rejected so discovery cannot escape the resolved source root.

```bash
python3 server/cookie_monster_alpha.py --source /srv/cookie-monster/staging-source --output /var/lib/cookie-monster-alpha/generated
```

## Metadata tooling and budgets

Alpha discovers `ffprobe`, `mediainfo`, and `exiftool` when installed. Tool failures become diagnostics and review items; they do not modify or discard source assets. Metadata extraction is constrained by one aggregate per-file time budget (20 seconds by default) and the ingestion run has a total time budget (300 seconds by default). Both are configurable through CLI arguments.

## Provenance, idempotency and duplicates

Each file receives a content-addressed `source_asset_id` of the form `sha256:<digest>`. Knowledge records include source pointer, ingestion actor/version, extraction method/version, confidence, review status, correction fields and a previous-record hash.

`knowledge-records.jsonl` and `audit.jsonl` are append-only across runs. `status.json` is the replaceable current-state snapshot. Knowledge records use a deterministic idempotency key derived from the source asset identity, source location, extraction method/version and recorded facts. Re-ingesting an unchanged staging asset reuses the existing knowledge record instead of creating a fresh unlinked record; the new read and the idempotent reuse are still appended to the audit trail. Legacy Alpha records created before the explicit idempotency field are recognized by deriving the same key from their existing provenance fields rather than rewriting history.

Duplicate candidates are exact byte duplicates grouped by `source_asset_id`; filename similarity alone is never sufficient.

## UI

The control surface includes dashboard/tooling state, intake browser ("What it ate"), exact duplicate groups, knowledge records ("What it learned"), review queue ("Needs human eyes"), provenance chain, and Fengus worker status. `demo-status.json` keeps the static UI usable before runtime-generated `status.json` is deployed; runtime status takes precedence automatically.

## Decisions resolved for Alpha

1. Code begins in `edge1-management-interface` as an isolated Cookie Monster subtree so it can reuse established Edge1 source, test, UI and deployment conventions without creating a premature second authority.
2. M0/M1 use synthetic or explicitly staged test data only.
3. No credentials are required for this foundation; real archive credentials remain a separate future boundary.
4. Big Bird hand-off integration is deferred until the ingestion contract is stable.
5. Human review ownership remains human; Alpha exposes the queue but no unreviewed production mutation endpoint.

## Milestone mapping

- **M0**: repository scaffolding, source/output separation, UI shell and read-only boundary.
- **M1**: discovery, SHA-256 identity, exact duplicate grouping, bounded metadata extraction, cross-run idempotency and append-only provenance against staging data.
- **M2**: draft/pending-review knowledge records with provenance and hash chain.
- **M3+**: bounded review mutations, Fengus isolation/runtime, archive-read audit integration, measurable acceptance against a non-production staging archive.
