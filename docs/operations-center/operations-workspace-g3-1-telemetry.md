# Edge1 G3.1 — trustworthy security telemetry and read-only drill-down

**Scope:** source-code-only staging on top of G3; not yet installed on Edge1. G1, G2 and the currently running G3 remain unchanged.

## Why this iteration exists

The operator's September 27 browser screenshot confirmed current Core and Network Defense snapshots but showed DNS reported healthy, IDS and Spamhaus unavailable, and firewall/Fail2ban/proxy/network sensor unknown. The original renderer colored every `observed: true` component green even when its state was unknown or unavailable. This was a UI evidence error, not proof of an actual firewall or IDS outage.

## Implemented changes

- **Explicit evidence classes.** A card is green only for a verified positive component state and present, current, explicitly available source checks. Ordinary observed or feed-ready states are neutral, not automatic health endorsements. Unavailable, unexpected, stale, unknown and failed supporting sources are warning colors. Explicit `not_deployed` is neutral and labeled. The parent source's freshness is evaluated independently.
- **Source-targeted diagnostics.** IDS checks security/correlation/core records when included in the existing exporter; Spamhaus checks feed and live-enforcement source records; DNS checks policy/network/core; firewall, Fail2ban, proxy and passive sensor use corresponding records when available. Only fixed source names and availability/freshness classifications enter the browser. Missing keys remain unverified, not invented.
- **Expandable card drill-downs.** Each security card explains the kind of observation it represents, whether current positive evidence was supplied, the recognized sanitized source states, and a read-only next step. It does not expose raw collector errors, paths, firewall rules, network addresses, private WireGuard peer names, credentials or attack payloads.
- **No misleading historic metrics.** Stale and unobserved components suppress metric values rather than presenting old counts as current. The interface uses DOM text content for status and diagnostic descriptions.
- **Appropriate boundaries.** A healthy DNS service observation is not a successful functional query test; a missing Spamhaus exporter is not evidence that the nftables production table was removed. No automatic rollback or live mutation has been enabled.

## Verification and deployment gates

The G3 offline suite adds positive-state-without-source tests, stale/failed source test fixtures, drill-down redaction checks, denial of green status for unknown/unavailable states, and stale count suppression. GitHub CI compiles the module and checks browser JavaScript; the existing G1/G2/G3 compatibility suites must pass.

These tests validate the *mapping*, not the actual live root cause of the missing IDS/Spamhaus observations. Before marking either component operational, inspect Edge1's existing read-only Network Defense and underlying collector source timestamps, report actual source availability and compare them with the active service state. A separate reviewed, pinned opt-in G3.1 installer and local browser verification will be required; do not assume GitHub commits update `/opt/edge1-operations-workspace-g3` automatically.

## Non-invasive live-source triage

`tools/operations/inspect_edge1_security_sources.py` produces a fixed-schema JSON report from the two existing Edge1 snapshot files. It reports core-service state for a small allowlist, each recognized network-defense component's reported state and observation flags, fixed-name collector source freshness, and parent snapshot age. It never emits raw diagnostic detail, addresses, alert payloads, rules, or secrets; it has no subprocess or filesystem mutation capability. Pin the exact reviewed commit before any operator-run check. Its output can establish where the **observation pipeline** is missing evidence, but neither proves firewall enforcement nor warrants remediation or automatic rollback.


## Actual Edge1 operator triage evidence — September 27, 2026

The operator fetched pinned commit `48f7eb368067085984685f953b2fda173465f897` and ran the read-only collector triage on Edge1. The Core and Network Defense parent snapshots were both fresh, each approximately 128 seconds old, generated near 20:01:17 UTC. Active core-service observations: CrowdSec, its firewall bouncer, AdGuard Home, Unbound and UFW. These active service states do **not** verify IDS operation, DNS resolution success or comprehensive firewall enforcement.

The **fresh** Network Defense aggregator reported IDS unavailable/unobserved; Spamhaus unavailable/unobserved; DNS healthy/observed; firewall and Fail2ban observed but state unknown; proxy and passive network sensor unknown/unobserved. All seven component enforcement-verified flags were false. Supporting sources `security`, `spamhaus`, `spamhaus_live_state`, `dns_policy` and `network` were **stale**, while `core_live`, `correlation`, `nftables_live_state` and `fail2ban_live_state` were current. This localizes the initial visible issue to stale or absent supporting telemetry, but does not establish why the producer snapshots are stale or whether the actual Spamhaus nftables table has changed.

**G3.1 rendering expectation:** DNS is not green while its DNS-policy/network sources are stale. The unknown firewall and Fail2ban statuses must not be green solely because `observed` is true. IDS and Spamhaus show warning with recognized stale dependencies. The network-defense parent being fresh never overrides stale child-source evidence. Avoid automated service restarts, feed updates and any firewall mutation until a separately verified root cause and recovery plan are available.

**Follow-up read-only evidence gate:** inspect timestamps/availability of the named source files, timer last/next scheduling and reported service states, plus an independent presence check of the production `inet bigbird_spamhaus` table; compare with current UTC. Do not dump raw collector JSON, rulesets, secrets or command environments into a chat transcript. An observed live-state file's freshness alone is not proof that the separate guarded automatic rollback prototype is safe.
