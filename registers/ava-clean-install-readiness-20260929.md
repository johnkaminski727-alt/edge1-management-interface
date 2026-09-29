# Ava clean-install readiness register — 2026-09-29

Status: **PRE-INSTALL / SOURCE CANDIDATE**

Candidate branch: `agent/ava-clean-install-integrated-20260929`

Contacts baseline:
- branch `phase-3b2-unified-contacts`
- commit `211a0ce1f41b1dcc11054c28e4fe17d8351b1637`
- tag `edge1-unified-contacts-3f-20260929`

## Closed in source

- Unified Contacts / Phone Intelligence Phase 3F is published and tagged.
- Ava controller work is rebased conceptually onto the published Contacts baseline through the integrated candidate branch.
- Ava has a bounded `contacts:read` source contract.
- `server/ava_contacts_gateway.py` uses the signed loopback Operations API instead of direct SQLite access.
- Contact adapter preserves assertion confidence separately from entity verification and sanitizes returned fields.
- Private Library production search now fails closed when live retrieval is unavailable.
- Fixture Library results are explicit development/test behavior only.
- Private Library production smoke test rejects fixture-backed mode by default.
- Library route-boundary documentation now matches the Private Access Gateway architecture.
- Ava Library collection selection is bounded/validated in the controller.
- A read-only clean-install preflight exists at `tools/ava_clean_install_preflight.py`.

## Rebuilt Edge1 preflight observed 2026-09-29

Read-only preflight from the live rebuilt Edge1 reported:

- current checkout: `phase-3b2-unified-contacts` at `211a0ce1f41b1dcc11054c28e4fe17d8351b1637`;
- Operations API active on loopback `127.0.0.1:8097`, health HTTP 200;
- private web gateway active on loopback `127.0.0.1:8098`;
- MCP listener present on loopback `127.0.0.1:8102`;
- Operations API service credential present;
- Unified Contacts database present;
- `bigbird-ai-gateway.service` inactive and `/opt/bigbird-ai-gateway/app/main.py` absent;
- Private Library database absent and `edge1-private-library-search.service` inactive;
- no listener on port 8091;
- the working tree contains newer uncommitted Unified Contacts expansion/messaging-adapter work.

The dirty worktree is now an explicit preservation gate. No Ava install, checkout
switch, reset, merge, or overwrite should occur until that work is captured safely.

## Still open before installation

1. Run the preflight on rebuilt Edge1 and capture the JSON result.
2. Inspect the rebuilt Big Bird gateway version and source shape before applying any gateway patch.
3. Integrate `ava_contacts_gateway.search_contacts()` into the actual Big Bird gateway request path and return sanitized `contact_sources`.
4. Verify the gateway independently enforces `contacts:read` and `include_contacts`.
5. Run Python controller, contacts adapter, Library, Unified Contacts, and gateway tests on Edge1.
6. Run the WW.CX PHP/browser regression suite against the Ava UI branch.
7. Build the fresh Ava install/rollback package only after the gateway preflight identifies the actual rebuilt baseline.
8. Verify Private Access Gateway authentication before exposing any human-facing route beyond loopback.
9. Perform reboot/restart and end-to-end acceptance against real Library and Contacts data.
10. Pin final commits, manifest, checksums, and release tag.

## Acceptance rule

Ava is not considered installed or production-ready merely because the UI,
controller, or source adapters are present. Acceptance requires a clean install
from pinned source, live-evidence Library mode, authenticated Contacts retrieval
through the Operations API, successful restart/reboot verification, and proof
that privileged/write authorities remain separately gated.
