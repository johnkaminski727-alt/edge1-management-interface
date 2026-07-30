# Edge1 Restricted Artifact Migration Register

Date: 2026-07-30  
Classification: internal security, publication-boundary, and evidence-planning record  
System: `edge1.ww.cx` / WW.CX Operations Center  
Source: `/edge1-status/` / `/var/www/edge1-status`  
Future target: `/edge1-ops/` / `/var/lib/wwcx-edge1-ops/releases`  
State: repository design; disabled, read-only, and not executed

## Objective

Record the repository-declared detailed artifacts and directory families that must be reconciled before a future authenticated `/edge1-ops/` staging release can be built or the anonymous detailed surface can be changed.

## Assets

| Asset | Function | Boundary |
| --- | --- | --- |
| `config/security/edge1-restricted-artifact-migration-manifest.json` | Exact known files, live-enumerated prefixes, source/target routes, scope requirements, and acceptance gates | Disabled; no staging, cutover, or deletion authorization |
| `server/edge1_restricted_artifact_manifest.py` | Validate the manifest and reconcile supplied read-only SHA-256 inventory evidence | No filesystem access or mutation |
| `tests/test_edge1_restricted_artifact_manifest.py` | Safety, coverage, mapping, unknown-preservation, collision, and non-mutation tests | Synthetic inventory only |
| `docs/security/edge1-restricted-artifact-migration-manifest-20260730.md` | Architecture, evidence, staging, cutover, removal, and rollback design | Repository only |

## Committed authorization state

```json
{
  "status": "design_only",
  "enabled": false,
  "staging_authorized": false,
  "cutover_authorized": false,
  "deletion_authorized": false,
  "source_mutation_allowed": false
}
```

Actions for exceptional conditions:

```text
unknown live artifact: preserve_review
duplicate target: block
missing known artifact: report
```

## Repository evidence

The starting inventory is derived from:

- `src/web/operations-center/index.html`;
- `deploy/operations-center/publish.sh`;
- `docs/operations-center/README.md`;
- `src/web/security/index.html`;
- referenced exporter and page sources.

This is repository evidence only. It is not a current live filesystem or route inventory.

## Manifest scope

| Class | Count | Treatment |
| --- | ---: | --- |
| Exact repository-declared artifacts | 23 | Exact source-to-target mapping |
| Live-enumerated prefix groups | 5 | Require fresh recursive host inventory |

Prefix groups:

```text
security/
network-defense/
bitcoin/
mining/
reports/
```

Every current mapping requires:

```text
edge1.status.detail.read
```

Target routes are validated against the registered `/edge1-ops/` access policy.

## Read-only inventory contract

Each supplied inventory record must contain only:

```text
path
sha256
mode
bytes
```

The validator requires the path to remain beneath `/var/www/edge1-status/`, validates a lowercase SHA-256, validates the octal mode and byte count, rejects unsafe paths, and rejects duplicate sources.

The module does not inspect, open, hash, copy, move, rename, chmod, chown, publish, route, delete, or prune a live file.

## Reconciliation contract

| Condition | Result |
| --- | --- |
| Exact known file | `stage_candidate`, exact provenance |
| File beneath approved prefix | `stage_candidate`, live-enumeration provenance |
| Unknown file | `preserve_review` |
| Missing exact known file | Report in `missing_known` |
| Duplicate target | Block reconciliation |
| Committed disabled state | `staging_ready:false`, `cutover_ready:false` |

Output records preserve the supplied hash, mode, and size and add only proposed target, route, classification, scopes, provenance, and action.

## Required acceptance before staging

- fresh authenticated route inventory;
- fresh authenticated filesystem inventory;
- SHA-256 inventory;
- protected source backup;
- target release validation;
- authorized route matrix;
- unauthorized route matrix;
- unknown artifacts resolved and preserved;
- target collisions resolved;
- source tree proven unchanged.

## Required acceptance before cutover or removal

The current register explicitly records:

```text
public_cutover_performed: false
detailed_artifacts_removed: false
traffic_controls_changed: false
live_change_authorized: false
```

Cutover requires its own explicit authorization and protected acceptance. Removal requires accepted cutover, complete target and route verification, publisher reconciliation, protected backup, and separate deletion authorization.

## Validation scope

Repository tests are intended to prove:

- committed authorization flags remain disabled and non-destructive;
- every mapping and prefix is unique, safe, scope-compatible, and covered by a registered restricted route;
- repository source paths exist when declared;
- literal Operations Center public references are covered;
- weakened preservation, unsafe paths, duplicate targets, unenumerated prefixes, and unsupported scopes are rejected;
- partial inventories map known files and preserve unknown files;
- complete synthetic exact inventories still do not become staging-ready under the disabled policy;
- malformed hashes, modes, sizes, paths, and duplicate source records are rejected;
- the reconciler contains no mutation, deployment, listener, Apache, or systemd operation;
- no migration installer exists.

Exact-head workflow and merge evidence remain pending.

## Live prerequisite status

No authenticated Edge1 execution path is available in the current repository-authoring session. No current live file count, ownership, mode, SHA-256, route, publisher, service, or completeness claim is made.

A fresh authenticated host pass must reconcile the entire live source tree, including unknown and prefix-contained artifacts, before the manifest can be considered complete for staging.

## Explicit non-authorization

This phase does not authorize or perform live inventory, source reads, hash calculation, copying, moving, renaming, release creation, mode or ownership changes, Apache changes, authentication changes, route changes, service changes, public cutover, detailed-artifact removal, pruning, DNS, certificate, firewall, traffic changes, or deletion.
