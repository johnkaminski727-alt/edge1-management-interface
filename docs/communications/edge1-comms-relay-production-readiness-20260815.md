# Edge1 Communications Relay Production Readiness Record

Date: 2026-08-15  
Target: WW.CX Edge1 Communications Relay 1.0.0

## Repository acceptance criteria

The production-ready repository revision must pass:

- Python compilation;
- `tests/validate_comms_relay.py` authenticated IRC and NNTP wire tests;
- safe-bind configuration tests;
- authentication throttle/rate-limit tests;
- per-account password iteration and SQLite WAL checks;
- moderated NNTP authorization and authenticated identity checks;
- retention pruning checks;
- candidate configuration apply/rollback checks;
- read-only control `/healthz` check;
- shell and JSON validation;
- deployment dry-run;
- normal repository CI and Edge1 Operator Validation.

## Operational acceptance criteria

A live Edge1 deployment is accepted only when the installer is run from a clean `main` checkout pinned to the intended commit and produces protected evidence showing:

- configuration validation passed;
- systemd unit verification passed;
- service is active when activation was requested;
- IRC, NNTP and control smoke tests passed;
- listeners remain on the approved addresses;
- installed unit/config hashes were recorded;
- no repeated restart loop or material service errors are present.

## Explicit exclusions

This readiness record does not authorize or claim completion of public DNS, firewall changes, certificates, Internet-facing listeners, IRC federation, NNTP peering, production message seeding, or external account onboarding.
