# Unified Communications — Remaining Backlog

Date: 2026-08-18

This backlog contains only work not completed by the safe repository/runtime convergence pass. Fresh Edge1 operator acceptance is complete for Messaging Gateway, BigBird messaging capabilities, the bounded Mail AI adapter, and the persistent loopback-only Communications workspace. Remaining items are kept explicit rather than inferred complete.

## Runtime verification

- [x] Run a fresh authenticated/operator-run read-only Edge1 acceptance pass for the safe available surfaces.
- [x] Confirm live Messaging Gateway `0.4.2`, BigBird `0.3.4-alpha.3`, Mail AI adapter bounded capabilities, and adjacent UC service active state.
- [x] Confirm Messaging Gateway and BigBird loopback listeners and verify the Communications workspace temporary listener rolls back cleanly.
- [ ] Complete fresh functional version/capability acceptance for Voice/SIP and Communications Relay beyond service-active evidence if required for final global runtime verification.
- [x] Install and accept the persistent loopback-only `wwcx-communications-workspace.service`.
- [ ] Confirm/attach the authoritative canonical communications-event snapshot/feed source used by the persistent workspace.
- [x] Record live rollback/checkpoint evidence for Messaging Gateway, BigBird, and Communications workspace runtime changes.
- [ ] Reconcile final safe-scope state and set `fresh_edge1_runtime_verified` true only after the intended canonical workspace feed and MMS security runtime are actually complete.

Persistent workspace acceptance on 2026-08-18 confirmed an enabled/running service from detached runtime source commit `a46ec4433033648c3428ce061318cdaf347a3605`, listener `127.0.0.1:8095` only, HTTP 200 health/readiness/index, honest zero-event state without a snapshot, HTTP 405 mutation rejection, unchanged `/opt/edge1-management-interface` worktree state, and adjacent UC services active. Rollback: `/tmp/edge1-uc-evidence-20260818T073658Z/rollback-communications-workspace-20260818T082857Z.sh`.

Operational warning retained: `free -h` showed approximately 1.5 GiB memory available and no recent kernel OOM evidence, but the 1 GiB swap allocation was fully consumed after activation. The workspace itself used about 11.4 MiB. This does not invalidate the workspace acceptance, but memory/swap pressure should be investigated before unnecessary broad service restarts.

## Mail correspondence

- [ ] Identify and explicitly authorize the authoritative native Mail Room correspondence/thread source for `mail.correspondence.read`.
- [ ] Build a sanitized bounded adapter that preserves native IDs, thread relationships, authorization boundaries, and provenance.
- [ ] Validate that outbound audit metadata is never substituted for correspondence bodies/history.

Freshly accepted and not blocked by the above:

- [x] `mail.status.read` local bounded status behavior.
- [x] `mail.draft.prepare` prepared-not-sent behavior with no send/mutation authority.

## MMS quarantine runtime

- [ ] Attach private quarantine storage with bounded retention and access policy.
- [ ] Attach a trusted malware/media scanner behind the fail-closed scanner callback boundary.
- [ ] Add operational readiness/health evidence for storage and scanner degradation.
- [ ] Design a separately authorized, audited release workflow; do not grant release to Private AI.

Fresh inspection found no installed `clamscan`, `clamdscan`, or `freshclam`, no active ClamAV service/socket, and no existing quarantine-storage candidate in the inspected paths. The live Messaging Gateway quarantine projection remains fail-closed and release remains unauthorized.

## Provider / production activation

These remain outside standing safe repository authority and require separate explicit approval where applicable:

- [ ] provider credentials/configuration;
- [ ] live SMS/MMS routing and transmission;
- [ ] live mail transmission where not separately authorized;
- [ ] SIP/carrier route or dialplan mutation;
- [ ] production call origination;
- [ ] emergency calling changes;
- [ ] number porting;
- [ ] STIR/SHAKEN changes;
- [ ] DNS/firewall/certificate/authentication-policy changes;
- [ ] quarantine release;
- [ ] provider contractual or financial actions.

## Product follow-through

- [ ] Populate evidence-backed cross-channel identity links only when authoritative evidence exists.
- [ ] Replace the intentionally empty workspace input with an approved bounded runtime aggregation feed from authoritative native channel sources.
- [ ] Run accessibility/browser acceptance on the persistently deployed Communications workspace if/when an authenticated browser route is approved.

## Durable fresh acceptance record

See `docs/communications/unified-communications-live-acceptance-20260818.md` and `.agent/unified-communications-validation-20260818.md` for the fresh operator evidence summary and retained rollback points.

No item above should be represented as complete until evidence exists for that specific layer.
