# Edge1 Restricted Artifact Migration Manifest

Date: 2026-07-30  
System: `edge1.ww.cx` / WW.CX Operations Center  
Source boundary: `/edge1-status/` and `/var/www/edge1-status`  
Future restricted boundary: `/edge1-ops/` and `/var/lib/wwcx-edge1-ops/releases`  
State: repository design only; disabled, read-only, and not executed on Edge1

## Objective

Create an exact, auditable starting manifest for moving detailed operational artifacts out of the anonymous `/edge1-status/` surface and into a future authenticated `/edge1-ops/` release.

This phase does not inspect the live host, copy files, build a release, alter routes, remove public artifacts, or authorize deletion. It records only artifacts and prefixes declared by the repository and requires a fresh authenticated live inventory before any staging decision.

## Why the manifest is required

The current Operations Center repository source directly references detailed Security, Network Defense, host, network, Git, incident, communications, bitcoin, mining, automation, and report outputs. The current publishing script also installs exporters and pages under `/var/www/edge1-status`.

A safe migration cannot treat that tree as a small fixed set of files. It must distinguish:

- exact repository-declared artifacts;
- directory families that require live enumeration;
- unknown live artifacts that must be preserved for review;
- missing expected artifacts that must be reported;
- target collisions that must block staging;
- later route cutover and deletion, which remain separate authorized actions.

## Repository evidence boundary

The manifest is grounded in:

```text
src/web/operations-center/index.html
deploy/operations-center/publish.sh
docs/operations-center/README.md
src/web/security/index.html
```

It also records the repository exporter or page source for each exact artifact when known.

This evidence is intentionally classified as `repository_declared_only`. It is not proof of the current live filesystem, current route behavior, completeness, ownership, modes, hashes, or current generated content.

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

Unknown artifacts use `preserve_review`. Duplicate target mappings use `block`. Missing known artifacts use `report`.

No manifest setting authorizes a live action by itself. Live staging, cutover, and deletion each require separate acceptance evidence and explicit authorization.

## Exact known artifacts

The manifest contains 23 exact repository-declared records, including:

- the Operations Center landing page and daily summary;
- Security, correlation, Network Defense, and mining pages;
- Security Operations, wallet, and mining status feeds;
- operations health, timeline, summary, automation, correlation, version, inventory, network, telephony, messaging, carrier, incident, and incident-history feeds;
- report index metadata.

Each record contains:

```text
source_relative
target_relative
classification
required_scopes
repository_source
```

Every current record requires the general restricted scope:

```text
edge1.status.detail.read
```

The future Suricata history surface remains separate and requires the additional history scope defined by the authenticated-boundary policy.

## Prefix groups requiring live enumeration

The repository indicates broader families beneath:

```text
security/
network-defense/
bitcoin/
mining/
reports/
```

These groups are not treated as complete inventories. A future authenticated filesystem pass must enumerate every regular file, symlink, directory, mode, owner, size, and SHA-256 value beneath them.

A live file covered by a prefix can become a staging candidate only after its exact relative suffix is validated and its target remains beneath the registered restricted route.

## Target boundary

Future release root:

```text
/var/lib/wwcx-edge1-ops/releases
```

Future route root:

```text
/edge1-ops/
```

The manifest validates every target against the registered routes and scopes in:

```text
config/security/edge1-authenticated-operations-policy.json
```

The reconciler does not create the target root or a release. It produces only proposed target-relative paths and route classifications.

## Read-only inventory contract

A supplied live inventory record must contain exactly:

```text
path
sha256
mode
bytes
```

Requirements:

- path must be beneath `/var/www/edge1-status/`;
- relative paths must reject traversal, absolute paths, duplicate separators, percent encoding, query strings, fragments, backslashes, and NUL;
- SHA-256 must be 64 lowercase hexadecimal characters;
- mode must be a four-digit octal string;
- byte count must be a non-negative integer;
- duplicate source records are rejected.

The reconciler never opens or hashes the live file itself. It validates inventory evidence supplied by a future authenticated read-only operator pass.

## Reconciliation outcomes

### Exact mapping

An exact manifest entry becomes a `stage_candidate` with:

- original hash, mode, and size evidence;
- proposed target-relative path;
- proposed `/edge1-ops/` route;
- manifest classification;
- registered route classification;
- required scopes;
- `exact` provenance.

### Prefix mapping

A live-enumerated file beneath an approved prefix becomes a `stage_candidate` with `prefix_live_enumeration` provenance.

### Unknown live artifact

A file not represented by an exact record or approved prefix is not ignored and is never deleted. It becomes:

```text
action: preserve_review
reason: not_in_repository_declared_manifest
```

### Missing known artifact

A repository-declared exact file absent from the supplied live inventory is reported in `missing_known`. Absence does not authorize creation, replacement, or deletion.

### Collision

Two sources resolving to the same target block reconciliation. Automatic overwrite or deduplication is forbidden.

## Readiness results

The reconciler returns separate booleans for:

```text
staging_ready
cutover_ready
```

The committed disabled manifest always returns both as false, even when a synthetic test inventory contains every exact known artifact.

Staging readiness additionally requires explicit enabled and staging-authorized flags, no missing known exact artifacts, and no unknown artifacts awaiting review.

Cutover readiness additionally requires explicit cutover and live-change authorization plus accepted route and release evidence. The current repository state does not satisfy or claim those conditions.

## Required fresh live inventory

Before any staging implementation, an authenticated Edge1 read-only pass must capture and protect:

- exact host, principal, clean `main`, and accepted repository revision;
- Apache version, virtual hosts, aliases, includes, authentication directives, modules, headers, redirects, and configuration test;
- local and public route matrices for every known and discovered artifact;
- complete `/var/www/edge1-status` filesystem inventory, including regular files, directories, symlinks, ownership, modes, sizes, and SHA-256 values;
- current publishers, exporters, timers, and services that write each artifact;
- current listener and proxy inventory;
- target capacity and conflicts under `/var/lib/wwcx-edge1-ops`;
- backup path, rollback commands, and protected evidence location;
- all unknown, duplicate, missing, stale, generated, historical, and operator-maintained artifacts.

The repository manifest must then be reconciled against that evidence. It must be updated through review if the live tree contains useful artifacts not represented here.

## Future staging sequence

Only after exact staging authorization:

1. verify fresh live evidence and repository revision;
2. preserve a complete read-only source inventory and protected backup;
3. reconcile every live artifact and resolve all unknowns and collisions;
4. build a new immutable restricted release without changing the source tree;
5. verify target file count, hashes, modes, ownership, route coverage, and scope coverage;
6. verify authorized and unauthorized route matrices against a fail-closed restricted staging route;
7. record terminal staging acceptance;
8. leave `/edge1-status/` and all source files unchanged.

## Future cutover and removal sequence

Cutover is a separate action after the restricted surface is accepted. It requires protected backups, exact Apache configuration validation, local and public route tests, TLS verification, and rollback.

Detailed-artifact removal is later still. It requires proof that:

- the authenticated route is accepted;
- authorized access succeeds with the correct scopes;
- unauthorized, unknown, and invalid access fails correctly;
- every intended artifact is present in the accepted restricted release;
- public minimized status remains healthy;
- no publisher will recreate removed detailed artifacts;
- deletion has been explicitly authorized.

Unknown artifacts, evidence, historical records, hashes, and backups are preserved by default.

## Rollback boundary

Repository reconciliation is read-only and requires no rollback.

A future staging rollback must remove only newly created unreferenced staging assets proven by exact evidence, restore prior unit/configuration files from protected backup, and preserve source files and migration evidence.

A future cutover rollback must restore the prior Apache route/include atomically, pass configuration validation, reload only after validation, and verify the complete route matrix. These operations are not implemented here.

## Safety boundary

No Edge1 host inventory, source read, hash calculation, copy, move, rename, mode or ownership change, release creation, Apache change, authentication change, route change, service change, listener, DNS, certificate, firewall, traffic control, public cutover, detailed-artifact removal, pruning, or deletion was performed or authorized.
