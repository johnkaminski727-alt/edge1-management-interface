# G3.3 — sanitized firewall and Fail2ban diagnostics

This increment extends the existing **localhost-only, SSH-tunneled G3 workspace**, not the production firewall. It renders strictly whitelisted numerical observations already contained in the existing Network Defense aggregate. It does **not** directly read root-owned JSON or execute nftables/fail2ban commands.

## New panels

- **Firewall aggregates:** tables, chains, base chains, rules, sets, maps, set/map elements, rules with counters, packet/byte counter totals and curated counts grouped by protocol family, hook, policy and verdict.
- **Fail2ban jail activity:** aggregate declared/observed jails, current/total failures, current/total bans, and strictly boolean installed/active/socket-reachable observations.
- Both expandable views are nested under their respective Security cards; an unknown component remains unknown even when its monitoring source is current. The existing **Evidence and next steps** drawers are retained.

## Privacy, fidelity and freshness

Only fixed dictionary keys are inspected. Numeric fields must be true integers between zero and 10^15; Boolean flags must be genuine booleans. Unrecognized properties, source paths, raw ruleset content, set elements, interface names, addresses, log messages, jail names and user identifiers are never sent to the browser. Aggregate numbers are rendered only when the parent Network Defense snapshot is current, the component is explicitly observed, and its specific `nftables_live_state` / `fail2ban_live_state` source record is available and not stale. A current source without supported metrics remains **No validated aggregate evidence** rather than displaying invented zeros.

Counter totals are historical values from the exporter, not rates or independent enforcement tests. Neither a green monitoring-source badge nor a nonzero rule count proves correct firewall policy, packet-path coverage, jail action success, or Spamhaus enforcement. Do not enable active Apply, start a privileged background service, broaden token access, restart security components or alter firewall tables for this phase.

## Acceptance

The existing G3 installer handles this as an optional pinned source-only upgrade after all G1/G2/G3.3 tests and exact reduced-archive preflight pass. Preserve existing G2 candidate state, private token and prior G3 package backup. After operator installation, restart the manually launched G3 server on the SSH-forwarded localhost port; verify expandable firewall aggregates and Fail2ban jail activity panels. The existing G3.2 production deployment stays unchanged until then.
