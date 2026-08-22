# Cookie Monster Alpha M6 Synthetic Acceptance

Status: source-level synthetic acceptance foundation. This is deliberately non-production and does not select, mount, credential, or modify a canonical archive.

## Purpose

M6 turns the Alpha safety claims into one repeatable acceptance run instead of a collection of disconnected tests. The harness creates a deterministic five-file staging dataset, including an exact duplicate and a small WAV file, then exercises the ingestion, provenance, review, Big Bird contract, and Fengus boundaries together.

Run with an ephemeral workspace:

```bash
python3 server/cookie_monster_acceptance.py
```

Retain the generated evidence in a known empty workspace:

```bash
python3 server/cookie_monster_acceptance.py --workspace /tmp/cookie-monster-m6-evidence
```

The harness refuses to populate a non-empty synthetic staging directory.

## Acceptance criteria

The generated `acceptance.json` records pass/fail evidence for:

- all synthetic assets ingested;
- at least one exact duplicate group detected;
- source byte hashes and mtimes unchanged across two runs;
- zero reported unauthorized source writes;
- zero source provenance gaps;
- zero knowledge-record hash-chain gaps;
- second run creates zero new knowledge records for unchanged input;
- audit history is physically append-only across the second run;
- one representative human-review record reaches `approved` through the bounded state machine;
- review transition completes inside a stated 5000 ms synthetic bound;
- one allowlisted Fengus data job completes;
- direct archive input to Fengus is rejected;
- zero Fengus jobs execute outside the allowlist;
- the Big Bird job envelope remains dataset-slug based and path/URL free.

## Evidence produced

A retained run writes only below its generated-output directory:

- `status.json`
- `knowledge-records.jsonl`
- `audit.jsonl`
- `review-decisions.jsonl`
- `review-state.json`
- `job-status.json`
- `acceptance.json`

The Cookie Monster operator UI reads `acceptance.json` when present and exposes an **M6 acceptance** screen. Absence of runtime acceptance evidence is displayed as not run; the UI does not turn source-level tests into a false live-health claim.

## Current development acceptance

The pre-publication local run on 2026-08-22 completed with:

- result: PASS
- 5 asset records / 4 unique content hashes
- 1 exact duplicate group
- 0 provenance gaps
- 0 unauthorized source writes
- 0 Fengus jobs outside the allowlist
- representative review latency: ~2 ms against a 5000 ms synthetic bound

These numbers are evidence for the deterministic synthetic harness, not a claim about a live or canonical archive.

## Boundary to the next phase

A real Edge1 acceptance run still requires a deliberately selected non-production staging dataset mapping and runtime packaging. The present Edge1 operator reports Big Bird in read-only mode, and the Edge1 repository runtime is not assumed to be synchronized to GitHub `main`; therefore this source milestone does not silently deploy or activate anything.
