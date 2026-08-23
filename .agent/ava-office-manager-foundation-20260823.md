# Ava Office Manager Foundation — 2026-08-23

## Objective

Establish the durable orchestration, user interface and authority foundation for Ava to
evolve from a read-only assistant/receptionist into a delegated executive assistant and
office manager.

## Implemented

- `server/ava_office_manager.py`
  - durable SQLite work queue and lifecycle states;
  - cross-channel artifact references;
  - standing instructions;
  - typed action proposals;
  - fail-closed authority evaluation;
  - sensitive-field rejection;
  - hash-chained audit records.
- `server/ava_appointment_workflow.py`
  - provider-independent availability, offer, selection and scheduling state machine;
  - typed `calendar.read`, `communication.draft`, and `calendar.event.create` intentions;
  - no provider side effects.
- `server/ava_attendant_session.py`
  - recording/transcription notice/consent state;
  - caller screening;
  - caller hold and private owner consultation;
  - accept, decline, voicemail, ask-Ava and attended-transfer states;
  - invariant that caller media is not joined to private owner consultation.
- `schemas/ava/call-record.schema.json`
  - protected call manifest for audio/transcript references, segments, call events and
    integrity hashes;
  - distinct caller/Ava, hold, private owner consultation, caller/owner and voicemail
    segments.
- `server/ava_office_manager_server.py`
  - fixed loopback-only read API on the source default port `8116`;
  - opens the office-manager database read-only;
  - exposes bounded summary/work/decision/instruction GETs;
  - rejects browser mutations.
- `src/web/ava-office/`
  - responsive/mobile-first Ava Office dashboard;
  - Work, Needs You, Calls, Appointments and Instructions views;
  - future warm-transfer controls rendered disabled until commissioning.
- `config/ava-office-manager-policy.json`
  - routine autonomy model;
  - external execution disabled;
  - explicit confirmation gates;
  - hard-blocked restricted domains.
- targeted unit/browser-contract CI in `.github/workflows/ava-office-manager.yml`.
- `docs/ava/office-manager-architecture.md`
  - long-term design and commissioning sequence.

## Deliberately not activated

- no production call answer, transfer or origination;
- no recording/transcription capture;
- no calendar provider read/write;
- no email/SMS send;
- no purchasing/travel commitment;
- no external provider credentials stored in the office-manager database;
- no public listener or routing change.

The repository policy ships with `execution_enabled: false`. Unknown and restricted
capabilities fail closed. Financial, legal, contract, credential, destructive and
emergency actions do not execute through the generic office-manager path.

## Remaining implementation / commissioning increments

1. Attach typed read adapters for authoritative calendar availability, detailed
   calls/voicemail and contacts.
2. Attach the authenticated Ava chat/controller to the durable work queue and read API.
3. Deploy the read-only loopback service and proxy the Ava Office UI through the existing
   authenticated WW.CX admin boundary.
4. Commission calendar create/update independently with preconditions, verification and
   rollback.
5. Build protected call-audio storage plus live streaming transcription behind the call
   manifest.
6. Connect the attendant state machine to a separately authorized Asterisk/FreePBX call
   control adapter and allowlisted owner destination; perform controlled live warm-transfer
   acceptance only after explicit production call-control authorization.
7. Commission narrow routine communications/follow-up adapters.
