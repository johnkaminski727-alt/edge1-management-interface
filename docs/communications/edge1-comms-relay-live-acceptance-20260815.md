# Edge1 Communications Relay Live Acceptance Record

Date: 2026-08-15  
Host: `edge1.ww.cx`  
Accepted revision: `99f16add875bdd6b185821d5491851bba9e12a68`  
Service: `edge1-comms-relay.service`

## Outcome

The private loopback WW.CX Edge1 Communications Relay 1.0.0 deployment is accepted as live and operational.

The accepted runtime endpoints are:

- IRC: `127.0.0.1:16667`
- NNTP: `127.0.0.1:1119`
- relay control/API: `127.0.0.1:8100`
- existing WW.CX telephony analytics: `127.0.0.1:8099` (preserved)

`network_exposure.enabled` remained `false`; no DNS, firewall, certificate, public listener or federation change was performed.

## Live validation evidence

The attended Edge1 deployment session verified:

- repository `main` fast-forwarded to the accepted revision;
- the migrated relay configuration validated successfully with control on port 8100;
- `tests/validate_comms_relay.py` passed production readiness;
- the deployment dry-run completed without changes;
- the transactional installer completed with bundled smoke test passing on attempt 2 of 12;
- `edge1-comms-relay.service` reported both `enabled` and `active`;
- a second independent bundled smoke test passed on attempt 1 of 12;
- IRC, NNTP and relay control listeners were present only on loopback;
- relay `/healthz` returned service `edge1-comms-relay`, status `ok`, version `1.0.0`;
- the existing telephony analytics `/healthz` on 8099 remained `status: ok` and `mode: read_only`;
- systemd showed the relay running under PID 138632 during the acceptance observation window.

## Deployment evidence paths

- Successful deployment evidence: `/var/lib/wwcx-deployment-evidence/comms-relay/20260815T183129Z`
- Pre-migration config backup: `/var/lib/wwcx-deployment-evidence/comms-relay/control-port-migration-20260815T183128Z/config.before.json`

These paths are on Edge1 and are not copied into the repository.

## Resolved activation incident

An earlier activation attempt used relay control port 8099 and failed with `OSError: [Errno 98] Address already in use`. Investigation established that 8099 was already the intended loopback endpoint for the WW.CX telephony analytics API. The relay control default was corrected to 8100 in PR #310. The later 18:31 UTC deployment used 8100, passed smoke tests, and preserved the 8099 telephony service.

The earlier journal traceback is therefore historical evidence of the superseded configuration, not an error from the accepted deployment.

## Acceptance boundary

Accepted:

- private Edge1 IRC service;
- private Edge1 NNTP reader/poster service;
- shared local identity/policy/storage/audit foundation;
- loopback read-only control/API;
- hardened systemd deployment;
- tested rollback-capable installer;
- runtime health and protocol smoke verification.

Not accepted or enabled by this record:

- Internet-facing IRC or NNTP;
- TLS certificate provisioning;
- DNS changes;
- firewall changes;
- IRC federation/server-to-server operation;
- NNTP peering;
- automatic IRC-to-NNTP mirroring;
- external account onboarding or production message seeding.

Those remain separately governed future changes.
