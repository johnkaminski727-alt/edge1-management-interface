# Ava Office Manager Foundation — 2026-08-23

## Objective

Establish the durable orchestration and authority foundation for Ava to evolve from a
read-only assistant/receptionist into a delegated executive assistant and office manager.

## Implemented

- `server/ava_office_manager.py`
  - durable SQLite work queue;
  - work-state transitions;
  - cross-channel artifact references;
  - standing instructions;
  - typed action proposals;
  - fail-closed authority evaluation;
  - sensitive-field rejection;
  - hash-chained audit records.
- `config/ava-office-manager-policy.json`
  - routine autonomy model;
  - external execution disabled;
  - explicit confirmation gates;
  - hard-blocked restricted domains.
- `tests/test_ava_office_manager.py`
  - lifecycle, audit, standing-instruction, sensitive-field and authority-boundary tests.
- `docs/ava/office-manager-architecture.md`
  - long-term design for appointments, cross-channel work, call recording/transcription,
    receptionist sessions and attended transfers.
- `.github/workflows/ava-office-manager.yml`
  - compile, policy parse and unit-test CI.

## Deliberately not activated

- no production call answer, transfer or origination;
- no recording/transcription activation;
- no calendar mutation;
- no email/SMS send;
- no purchasing/travel commitment;
- no external provider credentials stored in the office-manager database;
- no public listener or routing change.

The repository policy ships with `execution_enabled: false` and unknown/restricted
capabilities fail closed.

## Next implementation increments

1. Add typed read adapters for calendar availability, calls/voicemail and contacts.
2. Add appointment proposal/negotiation workflow using provider-independent schemas.
3. Add authenticated loopback Office Manager API and WW.CX admin/mobile queue UI.
4. Commission calendar create/update independently with verification and rollback.
5. Build the protected call archive and streaming transcription plane.
6. Add Ava attendant session control, then attended transfer to an allowlisted owner
   destination after explicit production call-control authorization.
