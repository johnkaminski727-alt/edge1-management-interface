# AVA Phase 3O Supersession Matrix — initial inventory

Date: 2026-10-02

Donor PR: #626 / `agent/ava-runtime-commissioning-20260930`  
Current browser/control lineage: `phase-3m-ava-ingress-policy-test-fix-20261001`

## Inventory result

The donor PR changes 26 files. Compared with the current Phase 3M head:

- 13 files are donor-only;
- 13 files exist on both lines but have different blobs;
- no donor PR file is already byte-identical to the Phase 3M version.

That means a wholesale merge/cherry-pick is not appropriate.

## Initial disposition

| Area | Files | Initial disposition | Reason |
|---|---|---|---|
| AVA/Big Bird gateway core | `services/bigbird-ai-gateway/app/*` | **Carry forward** | Runtime/backend implementation is absent from current Phase 3M and does not own Control Center presentation. |
| Gateway systemd/install | `deploy/systemd/bigbird-ai-gateway*`, `deploy/install-ava-readonly-gateway.sh` | **Adapt** | Runtime is useful, but deployment must be aligned with reviewed release-root / immutable-runtime practices before activation. |
| AVA browser-worker installer | `deploy/install-ava-browser-worker.sh` | **Adapt** | Signed queue/worker logic is still relevant; deployment must not assume the donor checkout is the UI release authority. |
| AVA signed acceptance helper | `tools/ava_gateway_signed_acceptance.py` | **Carry forward** | Useful acceptance tooling; no Control Center ownership. |
| AVA Contacts gateway | `server/ava_contacts_gateway.py` + test | **Adapt** | Needed capability, but must target the current Contacts contract and preserve current authenticated browser boundary. |
| AVA controller | `server/ava_agent_controller.py` + test | **Adapt** | Donor adds Contacts routing and approved-library collection handling; current Phase 3 version has independent changes and must not be overwritten. |
| Private Library runtime bootstrap | `tools/private_library/bootstrap_library_runtime.py`, runtime installer | **Adapt** | Runtime functionality remains useful; deployment/persistence assumptions require current-line review. |
| Private Library engine/test | donor engine files/tests | **Carry forward in isolated slice** | Backend-only source, absent from current line. |
| Private Library server/runbook/smoke tests | files present on both lines | **Adapt** | Donor hardens production fail-closed behavior, while current line has independent evolution. Merge semantics, not blobs. |
| Unified Contacts | `server/unified_contacts.py`, Contacts tests | **Adapt / do not overwrite** | Current live/working Contacts and separate CRUD work have advanced independently. Donor's provenance filter must be selectively reapplied if still required. |
| Operations API | `server/edge1_operations_api.py` | **Adapt / do not overwrite** | High-conflict shared control-plane file with newer current-line changes. Apply only bounded AVA/Contacts additions. |
| Phone intelligence gateway | existing on both lines | **Review** | Shared data boundary; compare semantics before deciding carry vs superseded. |
| CI workflows | existing on both lines | **Adapt** | Add donor-specific coverage without replacing newer Phase 3 validations. |
| Control Center/UI assets | none owned by PR #626 directly | **Superseded as deployment authority** | The donor checkout must never be used as the full UI publisher source. Current authenticated Phase 3 lineage remains authoritative. |

## Confirmed donor semantics worth preserving

Focused patch review confirms the donor AVA controller adds:

- explicit `contacts` source routing;
- `contacts:read` scope narrowing;
- contact evidence counts;
- bounded approved Private Library collection normalization;
- fail-closed invalid collection handling.

The donor Private Library server also removes silent fixture fallback in production by
default and returns `503 live_library_unavailable` unless fixture fallback is
explicitly enabled. This is desirable production behavior, but must be reconciled
with the current server version rather than replacing it wholesale.

The donor Contacts change adds a bounded `provenance_id` source filter and wires
that query parameter through the Operations API. This may still be useful for AVA
evidence lookup, but it must be applied against the current Contacts/CRUD code rather
than copied over it.

## First integration slice

Phase 3O.1A may safely stage source-only gateway runtime primitives and their isolated
tests because those paths do not exist in the current Phase 3M lineage. Deployment
scripts, shared Operations API, Contacts code, Control Center assets and live service
state remain untouched.

## Gate for the next slice

Before integrating the AVA controller or Contacts gateway:

1. inspect current Phase 3M controller behavior;
2. reapply only donor Contacts/library semantics;
3. run controller and Contacts tests in CI/isolated worktree;
4. verify no scope expansion;
5. preserve the authenticated `/edge1-ops/` browser architecture;
6. make no live publication from the donor checkout.
