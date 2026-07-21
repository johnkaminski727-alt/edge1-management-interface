# Production Node Promotion Checklist

## Scope

This checklist records readiness only. Completing it does not authorize production traffic, carrier routing, emergency calling, signing, porting, DNS, certificate, authentication, firewall, or authoritative-write changes.

## Candidate identity

- [ ] Candidate hostname and inventory identity are unique.
- [ ] Release commit is immutable and recorded.
- [ ] Private manifest is stored outside the public repository.
- [ ] Host-specific credentials and keys were generated independently rather than copied from Edge1.

## Isolated validation

- [ ] Manifest validation passes with every production-impact flag set to `false`.
- [ ] Host preflight evidence is complete.
- [ ] Required commands and runtime dependencies are present.
- [ ] Listener inventory matches the approved isolated policy.
- [ ] No production carrier trunk or customer-facing route is enabled.
- [ ] No emergency-calling route is enabled.
- [ ] No STIR/SHAKEN signing authority is enabled.
- [ ] No number-porting operation is enabled.
- [ ] No authoritative production write path is enabled.

## Service readiness

- [ ] Service configuration syntax checks pass.
- [ ] Local health checks pass.
- [ ] Service restart behavior is verified.
- [ ] Reboot persistence is verified.
- [ ] Logs reach the approved destination.
- [ ] Alerts trigger and clear as expected.
- [ ] Backup creation is verified.
- [ ] A restore test is documented.

## Rollback readiness

- [ ] Current production service remains available.
- [ ] Previous application and configuration releases are preserved.
- [ ] Candidate isolation procedure is documented.
- [ ] Objective rollback triggers are recorded.
- [ ] Rollback commands were tested without production impact.

## Controlled promotion boundary

The transition from `production-candidate` to `canary` requires a separate approved change record naming the traffic source, percentage or bounded workload, observation period, rollback operator, and exact rollback trigger. The transition to `active` requires successful canary evidence and a second explicit decision.
