# WW.CX Edge1 Operator Shell

## Status

The registry-driven WW.CX Edge1 Operator Shell was merged by PR #480 on 2026-08-20 at merge commit `4f77ebcde44df940390e5d03dc5af1872211faf9`.

Repository implementation is complete. Live publication is a separate acceptance step and must not be inferred from the merge. At the post-merge pre-deployment check, the bounded Edge1 Operator reported the live management checkout at detached `d326d4546abefa695a293266342a5c1075f010e2`; the loopback Operations API was healthy with mutations disabled; Apache and `wwcx-communications-workspace.service` were active; the Communications workspace listener remained loopback-only on `127.0.0.1:8095`.

Issue #476 is the implementation objective. Issue #59 and `docs/cx-admin/navigation-registry-readiness.md` remain provenance for the separate Business159/CX Admin discovery work; the CX Admin discovery registry is not authority for this Edge1 shell.

## Architecture

The shell is a navigation and operator-context layer, not a new authorization layer and not a replacement backend.

Canonical source:

- `config/edge1_operator/navigation_registry.json`

Shared shell assets:

- `src/web/operator-shell/shell.css`
- `src/web/operator-shell/shell.js`

Integrated specialist surfaces:

- Operations Center: `src/web/operations-center/index.html`
- Communications workspace: `src/web/communications/index.html`
- Security Console: `src/web/edge1-ops/security/index.html`

The Operations Center and Communications workspace consume shared static shell assets. The Security Console keeps its existing single-inline-style/single-inline-script contract so the authentication adapter can continue applying CSP nonces; its inline shell code reads the same canonical navigation registry when available and falls back only to the accepted Operations Center route.

Specialist applications remain specialist applications. The shell does not flatten their backend boundaries, convert them into a single SPA, or merge Store Admin into Edge1 Operations.

## Information architecture

The registry may describe verified or evidence-backed modules that are not yet safe to expose as live navigation. Only modules whose registry state is `accepted_live` and whose `browser_route` is a rooted browser path are rendered as navigation targets.

The initial accepted live set is deliberately conservative:

- Operations Center — `/edge1-status/`
- Security Operations — `/edge1-status/security/`
- Security Correlation — `/edge1-status/security/correlation.html`
- Network & DNS Defense — `/edge1-status/network-defense/`
- Bitcoin Operations — `/edge1-status/bitcoin/`
- Mining Operations — `/edge1-status/mining/`

The Communications workspace and its specialist Mail, SMS/MMS, Voice/SIP, and News/Relay tools remain represented according to their verified runtime evidence but are not silently promoted through an unverified public browser path. The WW.CX AI browser route likewise remains non-navigable until browser production acceptance is explicitly verified.

## Registry contract

Each module declaration records operator-facing metadata and evidence rather than inferring authorization from filenames. Fields include:

- stable module ID;
- label, section, order, description, and icon ID;
- verified browser route when one is accepted;
- authorization/scope metadata;
- availability state and predicate;
- desktop/mobile visibility;
- specialist/top-level classification;
- safety/read-write class;
- optional status source and ToolBox eligibility;
- provenance.

The top-level safety contract is fail-closed. It states that navigation does not grant authorization, generic execution is not authorized, production communications traffic is not authorized, mutations are disabled, and unknown status is not healthy.

Validation is implemented by:

- `tools/edge1_operator/validate_navigation_registry.py`
- `tests/test_edge1_operator_navigation_registry.py`

## Authentication and authorization boundaries

The shell never substitutes for server-side authorization.

Security Console integration preserves the existing WW.CX-to-Edge1 handoff and direct-route protections. The console retains its session endpoint, CSRF cookie/header handling, validation scope check, logout flow, same-origin credentials, and fail-closed behavior. The only mutation-shaped request exposed by that console remains the pre-existing allowlisted configuration validation operation; it does not restart/reload services, rotate material, or change traffic.

Communications preserves the distinction between read, prepare, send, and production authorization. `read != write`, `draft != send`, and `runtime ready != production authorized` remain explicit invariants. The workspace remains loopback-only and rejects mutation verbs.

Navigation visibility is never an authorization decision. Direct requests to protected routes must continue to be authorized by their owning service.

## Operator experience

Desktop uses a persistent left navigation rail from the canonical registry. Narrow layouts use a drawer generated from the same filtered registry.

The shell provides:

- active-location indication with `aria-current`;
- breadcrumb/operator context where the host surface has it;
- explicit read-only/mutation-disabled/production-traffic safety state;
- Ctrl/Cmd+K navigation palette;
- browser-local favourites and recent modules;
- contextual ToolBox links from the same registry metadata;
- visible keyboard focus;
- Esc close behavior for palette and mobile drawer;
- reduced-motion accommodation;
- an Operations Center escape route if registry loading or safety validation fails.

The palette is navigation-only. It does not evaluate strings, dispatch arbitrary commands, call module-defined action endpoints, or turn registry data into execution authority.

## Failure behavior

Registry, status, or telemetry failures degrade visibly and safely.

- Unknown telemetry is warning/neutral, never healthy by default.
- A rejected or unavailable registry does not create an empty trap; the shared shell exposes an Operations Center escape link and marks the navigation safety state unknown.
- Security Console falls back only to Operations Center navigation and retains its own authenticated application behavior.
- No failure path promotes staged modules, invents URLs, or expands authorization.

## Adding or changing a module

1. Establish the real browser route and ownership from repository/runtime evidence.
2. Establish the route's actual authentication and scope requirements from the owning service; do not infer them from the path or filename.
3. Add or update the canonical registry entry with provenance and a conservative availability state.
4. Keep unverified browser routes non-navigable.
5. Run the registry validator and shell tests.
6. Run the owning subsystem's existing validation suite, not only shell-specific tests.
7. If the route is to become `accepted_live`, capture browser/auth acceptance evidence and verify direct-route authorization before changing availability.
8. Deploy with a rollback point and verify listeners/mutation boundaries after publication.

Do not add API endpoints, callbacks, action URLs, payload/include paths, login/logout mechanics, or arbitrary execution targets to the operator navigation registry.

## Validation

The dedicated workflow is `.github/workflows/edge1-operator-shell.yml`.

The merged implementation was accepted only after the exact PR head `ae7a59446904ce68c42636fc23364ae9f8b7654f` passed all of:

- `Validate repository`
- `Edge1 Operator Validation`
- `Unified Communications Validation`
- `Edge1 Operator Shell`

Focused coverage includes registry schema and duplicate/route safety, fail-closed behavior, responsive/accessibility hooks, shared-shell integration, Security Console registry/fallback behavior, Communications read-only boundaries, JavaScript parsing, Python compilation, and publisher shell syntax.

## Operations Center publication and rollback

`deploy/operations-center/publish.sh` is dry-run by default.

Dry run:

```sh
cd /opt/edge1-management-interface
./deploy/operations-center/publish.sh
```

Apply:

```sh
sudo ./deploy/operations-center/publish.sh --apply
```

Apply creates a timestamped backup under `/var/backups/wwcx-operations-center-<UTC timestamp>/`, records whether each prior file existed, and writes an executable `rollback.sh`. It then publishes only the Operations Center page plus `shell.css`, `shell.js`, and the canonical registry copy used by the browser.

Rollback uses the exact path reported by the apply step:

```sh
sudo /var/backups/wwcx-operations-center-<UTC timestamp>/rollback.sh
```

Do not guess the timestamp.

## Communications workspace deployment

The existing deployment boundary remains `deploy/install-wwcx-communications-workspace.sh`. It is dry-run by default, requires the service account and listener preconditions, captures the previous systemd unit state, installs/restarts only `wwcx-communications-workspace.service`, waits for loopback health, verifies readiness/events JSON, verifies POST rejection with `mutation_authorized=false`, and refuses wildcard exposure on port 8095.

No reverse proxy or public listener is introduced by that installer.

## Live acceptance checklist

Live acceptance is not complete until all applicable checks are observed after deployment:

- live management checkout is the intended merged commit or documented descendant;
- Operations Center loads the new shell and canonical registry;
- desktop navigation and narrow/mobile drawer use the same accepted registry set;
- visible focus, skip link, Esc behavior, and Ctrl/Cmd+K navigation work;
- active location is visible;
- registry failure leaves an Operations Center escape path;
- Security Console retains direct-route auth, session, CSRF, validation, logout, CSP nonce, and mutation-denial behavior;
- Communications remains read-only and loopback-only; no call/message/mail/quarantine/routing production authority appears;
- accepted specialist status pages remain reachable;
- Apache and directly affected services are healthy;
- listener exposure has not expanded;
- Operations API still reports mutations disabled;
- rollback artifacts are retained;
- browser acceptance evidence is recorded without secrets or session tokens.

If an authenticated live browser path is unavailable, record that acceptance as pending rather than inferring success from repository tests.

## Provenance

- Issue #59 — CX Admin discovered-route provenance; discovery-only registry remains separate.
- Issue #476 — integrated Edge1 Operator Shell objective and safety invariants.
- PR #480 — implementation and exact-head CI evidence.
- Merge commit `4f77ebcde44df940390e5d03dc5af1872211faf9` — repository integration point.
