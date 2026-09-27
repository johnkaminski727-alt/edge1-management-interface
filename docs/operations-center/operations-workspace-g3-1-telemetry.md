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

## Follow-up Edge1 read-only producer inspection — 20:06 UTC, September 27

The operator's new terminal evidence shows `core-status.json` and `network-defense/data/network-defense.json` both updated at 20:05:57 UTC, approximately 32 seconds before the 20:06:29 UTC check. The visible systemd timers `edge1-security-correlation-observation.timer`, `edge1-crowdsec-observation.timer`, and `edge1-network-defense-observation.timer` had recently fired and had next activations scheduled around 20:07:56–57 UTC. The matching `edge1-network-defense-observation.service` was inactive/dead when sampled; this is consistent with a timer-triggered one-shot service, *not proof of a failed collector*. The **production `inet bigbird_spamhaus` table was independently confirmed present by a root-authorized `nft list table` presence test**. This does not prove the nft table's full contents, active hooks or drop-set correctness, nor resolve guarded rollback safety.

The unprivileged `wwadmin` file test reported `MISSING or inaccessible` for `security-operations.json`, `operations-network.json`, `dns-defense-policy-status.json`, and root-owned Spamhaus/nftables/Fail2ban state files. Since `-f` conflates nonexistence and inaccessible traversal, this result **does not establish that every file is missing**. The collector source records nonetheless classify security, network, DNS policy and Spamhaus input as stale. A follow-on privileged **metadata-only** `stat` should distinguish absent files from inaccessible files and compare actual mtimes, while the service `systemctl show` metadata should distinguish disabled/not-installed historical producers from one-shot collectors. Do not restart services, regenerate feed material or change production nftables from these observations. The `edge1-core-observation.timer` was not returned by the user's grep pattern, so no claim about that timer's presence/absence is supported by this particular grep result.

## Privileged metadata confirmation — Edge1 20:08 UTC, September 27

The operator ran a second, privileged **metadata-only** inspection at 20:08:20 UTC. None of the following five legacy dependency files passed root's regular-file check at the configured path:

- `/var/www/edge1-status/security-operations.json`
- `/var/www/edge1-status/operations-network.json`
- `/var/www/edge1-status/dns-defense-policy-status.json`
- `/var/lib/bigbird-networking/spamhaus/summary.txt`
- `/var/lib/bigbird-networking/spamhaus/live-state.json`

This is stronger evidence that the expected producer artifacts **are absent at those paths** (although `test -f` does not distinguish absent files from abnormal root-level traversal failures, and does not rule out revised output paths). It is not evidence that the corresponding runtime protection is disabled.

Both current dedicated security observation files **do** exist: `/var/lib/bigbird-networking/nftables/live-state.json`, updated 20:08:17.171 UTC (2,499 bytes), and `/var/lib/bigbird-security/fail2ban/live-state.json`, updated 20:08:17.035 UTC (1,371 bytes). All four current core/CrowdSec/Network Defense/Security Correlation service/timer pairs were listed: the service units are `static` one-shots and all four timers `enabled`. `edge1-core-observation.timer` and `edge1-network-defense-observation.timer` were both `loaded/active`, last triggered 20:08:16 UTC. The independent production Spamhaus nft table presence check from the preceding operator run was positive.

**Action:** correct the G3.1 classifier: `available: false` plus `stale: true` from a missing file must be rendered **unavailable**, not `stale`; reserve **stale** for `available: true` with an expired observation. Keep DNS in a mixed-evidence warning state while its historical policy/network artifacts are absent, despite currently observed active AdGuard Home and Unbound services. Present current nftables and Fail2ban live-state evidence without inferring complete enforcement; the aggregate firewall/Fail2ban state remains unknown pending a separately reviewed mapping from the known live-state schema. Do **not** fabricate placeholder legacy files, restart production services or force an unapproved Spamhaus updater.

The existing Network Defense aggregator combines current core/CrowdSec observations with a larger historical exporter graph. Until a separately approved migration removes obsolete dependencies or supplies explicitly reviewed current-source adapters, it will continue to publish a fresh **parent** snapshot containing unavailable **child** sources. G3.1's diagnostics are the immediate safe interim solution.


## G3.1 first install attempt: missing packaging dependency, safely stopped

On the operator's first attempt to install pinned revision `3e2d82a5121dc986d693e5b6e824b90963f117eb`, the `--check` preflight completed G1/G2 test groups (8+6+4) but stopped before G3 installation with `ModuleNotFoundError: No module named 'inspect_edge1_security_sources'`. The reduced `git archive` extraction omitted a G3.1 triage helper newly imported by `tests/validate_edge1_operations_g3.py`; full-checkout CI did not catch that reduced-archive omission. **The installer never reached `--apply`**, so the previously installed G3 remains unchanged.

The revised installer explicitly requires and installs the helper, includes it in the G3 SHA-256 payload manifest, and CI now reproduces the **exact reduced operator-archive extraction** and exercises `--check` from that extracted directory. The next operator command must pin the new CI-verified commit and include `tools/operations/inspect_edge1_security_sources.py` in its `git archive` list. No live firewall or network modifications are part of the correction.
