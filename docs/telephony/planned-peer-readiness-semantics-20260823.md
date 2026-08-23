# Planned SIP peer readiness semantics — 2026-08-23

## Finding

Fresh read-only Edge1 telephony status showed one healthy interconnect and one failed interconnect. Repository inspection established that the failed entry was not a configured carrier trunk:

- carrier `lab-carrier-001` has lifecycle `planned`;
- peer `lab-carrier-001-peer` has endpoint value `pending`;
- the stored July OPTIONS failure was a DNS-resolution error caused by attempting to resolve that placeholder endpoint.

Treating that record as an operational trunk failure makes the dashboard imply a 1/2 trunk-health result even though only one peer is currently configured for a meaningful health check.

## Corrected model

The read-only telephony status server now distinguishes carrier lifecycle/configuration from health observations.

A SIP peer is health-check applicable only when:

- its endpoint is a non-empty concrete value other than `pending`; and
- its parent carrier lifecycle is not `planned` or `pending`.

Non-applicable peers remain visible as `planned` but no longer contribute to operational `trunks_total`, `trunks_healthy`, latency or success-rate values.

The status metrics now expose:

- `trunks_healthy` — healthy configured/applicable peers;
- `trunks_total` — configured/applicable peers only;
- `trunks_planned` — peers intentionally excluded because they are not configured yet.

Acceptance and carrier-lifecycle payloads use the same rule, so a historical failed probe against a placeholder does not masquerade as a current carrier interoperability failure.

## Additional correctness fix

Carrier lifecycle peer membership now follows each registry peer's explicit `carrier_id`. The old implementation inferred membership from peer-ID string prefixes, which could omit a legitimately associated peer whose name did not start with the carrier ID.

## Safety

This is reporting/model logic only. It does not resolve the placeholder endpoint, send SIP OPTIONS, originate a call, modify Asterisk, alter a trunk/route/dialplan, configure credentials, change DNS/firewall/certificates, or claim carrier readiness.

A planned peer becomes operationally testable only after a real endpoint and carrier state are deliberately configured under the appropriate activation authority.
