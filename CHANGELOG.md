# Changelog

## 2026-07-18 — Time Authority rollout simulation

- added an end-to-end, non-production simulation for both server installers;
- verified Edge1 unit staging, repeated collection, live API mode, and CSV export;
- verified shared-host permissions, repeated installation, and cron idempotency;
- added strict simulation guards that reject the production unit path and real `systemctl`.

## 2026-07-18 — Time Authority readiness sweep

- corrected the shared collector's remaining Python 3.6 type-annotation incompatibilities;
- added repository CI, including a real Python 3.6 container import check;
- added Edge1 preflight and production smoke-test scripts;
- made shared-host cron installation idempotent and self-verifying;
- added a spreadsheet-ready CSV endpoint and dashboard download action;
- added stricter browser security headers, NTP response-peer validation, and deployment regression checks.

## 2026-07-18 — WW.CX Time Authority

- registered the Netnod, NIST, and Cloudflare sources verified from Edge1 and shared hosting;
- added independent Edge1 and shared-host RTT collectors using a common JSONL schema;
- added a localhost-only read API and responsive Big Bird Time Authority dashboard;
- added baseline measurements, deployment timers, validation, and an operator runbook.

## 2026-07-18 - Private Library Search Managed Service

- Added a hardened localhost-only systemd unit for the search wrapper.
- Added a root installer with checkout-path and prerequisite checks.
- Added a service smoke test covering bind scope, search mode, and the
  disallowed-collection guard.
- Added a repo-side asset validation test (no root or systemd required).
- Added an operator runbook with install, verify, override, and rollback steps.
- Added a service register with pending operator actions.
- Preserved the localhost-only/no-route-exposure/read-only boundary.

## 0.1.0 - 2026-07-16

- Initialized Edge1 management interface source repo.
- Added read-only Private Library Search module brief.
- Added mobile responsive behavior rules.
- Added API contract fixture for private-library search results.
- Added repository safety boundaries for secrets and large archive files.
- Added dependency-free static Private Library Search UI.
- Added fixture-backed search, result cards, detail panel, and copy actions.
- Added static UI validation script.

## 2026-07-17 - Handoff Organization

- Added handoff documentation for the Edge1 management interface.
- Documented the live-direct private library search bridge.
- Added a restricted private library backup script and runbook.
- Added a handoff register for operator-facing status and next actions.

## 2026-07-17 - Autonomous Completion Controls

- Added autonomous project charter, guardrails, restore index, and acceptance checklist.
- Added a master autonomous completion register.
- Added a read-only handoff verifier for repo, docs, backup, and live search state.

## 2026-07-17 - Combined Registers

- Added a combined project register covering Edge1 management, Big Bird gateway,
  private library imports, handoff/restore files, backups, and adjacent connector
  tracks.
- Added an autonomous-completion register index.
- Extended handoff verification to require the combined register files.

## 2026-07-17 - AI Filesystem Connector Phase 2

- Added `bin/bigbird-fsctl` for staged proposal intake and inspection.
- Added conservative path/content validation for staged proposals.
- Added JSONL audit logging for stage, list, show, diff, and validate actions.
- Added a Phase 2 smoke validation test.
- Preserved the no-apply/no-root-service/no-auto-approval boundary.

## 2026-07-17 - AI Filesystem Connector Phase 3

- Added approval metadata commands for staged proposals.
- Added rejection metadata commands for staged proposals.
- Added approval status inspection.
- Added JSONL audit logging for approval-state actions.
- Preserved the no-apply/no-root-service/no-auto-approval/no-rollback boundary.

## 2026-07-17 - Spamhaus Filtering

- Added an nftables-based Spamhaus DROP/EDROP update script.
- Added systemd service and timer units for recurring refresh.
- Added installer and smoke-test scripts.
- Added operator runbook and register entries for Edge1 Spamhaus filtering.

## 2026-07-17 - AI Filesystem Connector Phase 4

- Added operator-controlled apply for approved staged proposals.
- Added configurable project path allowlist and hard deny rules.
- Added pre-apply snapshots, post-apply verification, and rollback metadata.
- Added JSONL audit logging for apply actions.
- Preserved the no-auto-approval/no-AI-apply/no-root-service/no-rollback-execution boundary.

## 2026-07-17 - Spamhaus Handoff Finalized

- Added final Spamhaus completion handoff and archive checklist.
- Updated Spamhaus runbook with verified live counts and reporting workflow.
- Added durable Edge1-to-ww.cx Spamhaus status push script.
- Updated Spamhaus register with final operational evidence and rotation tasks.
