# CrowdSec Operations Center integration plan

Status: design prepared; implementation and live acceptance pending. Based on the approved original Edge1 NOC Observe/Investigate roadmap, existing read-only Operations Center v1.4 and operator-reported CrowdSec production acceptance from September 27, 2026.

Source inventory: `src/web/operations-center/index.html` consumes read-only operational snapshots. `tools/operations/validate-operations-center.sh` checks existing portal artifacts. Network Defense already distinguishes observed telemetry, feed readiness and verified enforcement. Do not infer a running sensor from historical repository documentation without current checks.

Proposed versioned collector: publish sanitized UTC observation timestamps, IPv4/IPv6 INPUT hook states, IPv4 VPN FORWARD hook and directional counter states, explicit IPv6 forwarding-disabled status, bouncer freshness if measured, bounded blacklist counts, source provenance, service health and independently verified recovery-test status. Unknown and stale states must never be shown as healthy. Do not expose secrets, peer details, full blacklists or raw firewall rules.

Next implementation gates: inspect contemporary collectors and contracts read-only; add a least-privilege allowlisted exporter and schema fixture; validate healthy, missing, stale and partial evidence states; integrate read-only Security and Network views; run existing repository validators; obtain an authenticated operator review before publishing. Record final evidence and controlled deployment separately. No firewall, VPN or DNS mutation is authorized by this document.

Separate open operational tests: active-hook UFW reload with independent recovery, blacklist freshness and exception review, and optional inbound-forward traffic test. The accepted infrastructure deployment is not completion of the original proposal's canonical candidate/review/apply engine.