# Ava Executive Assistant and Office Manager Architecture

Status: foundation implementation
Date: 2026-08-23

## Product objective

Ava is intended to become one continuous personal assistant across chat, telephone,
email, SMS/MMS, calendar, contacts, documents, appointments, vendors and office work.
The user gives Ava outcomes; Ava decomposes them into clerical work, tracks progress,
uses approved channels, and interrupts the owner only when a decision crosses a defined
authority boundary.

This is deliberately not implemented as a collection of unrelated bots. A single durable
work item may link a phone call, transcript, email thread, calendar event, document,
shipment, invoice reference and follow-up task while keeping the source systems
independently authoritative.

## Design principles

1. **Outcome-oriented delegation** — a request such as "handle the equipment return"
   creates a durable work item with a desired outcome, not a one-shot chat response.
2. **One work queue across channels** — calls, mail, messaging, calendar and documents
   attach to the same work item by opaque source references.
3. **Standing instructions are explicit policy** — preferences and prohibitions are
   visible, editable rules rather than hidden prompt memory.
4. **Planning is separate from execution** — Ava may understand, research and prepare
   work without automatically gaining permission to send, book, call, purchase or
   modify a system.
5. **Least authority** — every external action maps to a narrow named capability and a
   separately commissioned adapter/control plane.
6. **Fail closed** — unknown capabilities, credentials, contracts, legal/financial
   actions, destructive actions and emergency calling do not become executable merely
   because the model proposes them.
7. **Auditable state transitions** — work creation, state changes, linked artifacts,
   instructions and action proposals are hash-chained.
8. **AI failure must not equal service failure** — telephone, calendar and messaging
   systems retain deterministic fallback behavior when Ava is unavailable.

## Foundation delivered in this increment

`server/ava_office_manager.py` provides the first durable core:

- SQLite-backed work items;
- lifecycle states: `new`, `working`, `waiting_external`, `needs_owner`, `scheduled`,
  `completed`, and `cancelled`;
- priority ordering;
- cross-channel artifact references;
- persistent standing instructions with `deny`, `require_confirmation`, and `prefer`
  effects;
- action proposals with explicit capability names;
- authority classification and fail-closed policy evaluation;
- sensitive-field rejection;
- hash-chained audit records;
- a summary surface suitable for a future Ava dashboard.

`config/ava-office-manager-policy.json` is intentionally shipped with
`execution_enabled: false`. This lets the workflow and authorization model be exercised
without originating calls, sending messages, creating provider appointments, spending
money or modifying production routing.

## Authority levels

### Observe

Read already-authorized information. Examples: calendar availability, call status,
communications context, office-manager queue state.

### Prepare

Create a draft or proposed result without external effect. Examples: proposed meeting,
email draft, itinerary options, quote comparison.

### Routine

Normal clerical actions that may eventually run autonomously after the relevant adapter
is separately commissioned. Examples: create an ordinary calendar appointment, send a
routine confirmation, perform receptionist screening, complete an attended transfer to
an approved destination.

### Conditional

Actions that require explicit confirmation or additional policy conditions. Examples:
call origination, cancelling an appointment, booking travel or committing a purchase.

### Restricted

Actions that do not execute through the office-manager authority path. Financial
transfers, contracts/signatures, legal actions, credentials, destructive actions,
emergency calling and uncommissioned capabilities require a separate explicit path and
fail closed here.

## Work item model

A work item is the durable unit of delegation. Minimal fields are:

- stable opaque work ID;
- title;
- desired outcome;
- state and priority;
- originating channel and opaque source reference;
- owner;
- optional due time;
- created/updated timestamps;
- linked artifacts.

Examples:

- `Arrange dentist appointment`
- `Handle Telus handset return and verify credit`
- `Schedule follow-up with carrier engineering`
- `Return calls received while unavailable`

Artifacts are references rather than copied provider records. Example kinds include
`call`, `transcript`, `recording`, `email_thread`, `message_thread`, `calendar_event`,
`document`, `shipment`, and `contact`. Source systems remain authoritative.

## Standing instructions

Standing instructions are explicit operational policy such as:

- do not schedule meetings before 10:00;
- prefer Tuesday through Thursday afternoons;
- always screen sales calls;
- approved family/VIP callers may bypass ordinary screening;
- never create a calendar event in a specified category without confirmation.

The foundation stores the instruction statement and its policy effect. A later policy
compiler will convert structured settings into deterministic constraints used by
calendar, communications and telephony adapters. Free-form text alone must not become a
privileged execution rule.

## Receptionist and attendant architecture

The telephone system is a channel into the same office-manager workflow.

### Inbound call flow

1. Asterisk/FreePBX receives the call through the existing production routing path.
2. The Ava attendant application is offered the call through a narrowly scoped call
   session adapter.
3. Required recording/transcription notice or consent policy is applied before content
   capture where applicable.
4. The call archive creates one logical call record and immutable identifiers.
5. Audio is recorded to protected storage and streamed to transcription.
6. Speaker/timestamp transcript events are delivered to the attendant session.
7. Ava identifies the caller, gathers purpose, answers approved routine questions, or
   creates/updates a work item.
8. If the owner is needed, Ava performs an attended transfer workflow.
9. On hangup, the final transcript, summary, action items and call metadata are linked to
   the work item.

### Warm transfer

A warm transfer is a state machine rather than one generic "transfer" command:

`caller_with_ava -> caller_held -> private_owner_consult -> accepted|declined|timeout`

If accepted:

`accepted -> bridge_caller_owner -> ava_departed_or_copilot`

If declined or unanswered:

`declined|timeout -> caller_returns_to_ava -> message|voicemail|callback_work_item`

The caller cannot hear the private owner consultation. The owner receives a concise
briefing and may accept, decline, send to voicemail, ask Ava to obtain more information,
or request a callback arrangement. External transfer destinations are allowlisted by the
call-control service; the model does not receive arbitrary dialing authority.

### Call evidence and working data

The design separates three views:

1. **Protected evidence** — original audio, channel-separated audio when available,
   integrity hashes and restricted raw call evidence.
2. **Detailed operational record** — CDR/routing/transfer state, timestamps, participant
   references, disposition, hold/consult events and transcription provenance.
3. **Ava working view** — transcript, caller/contact context, summary and bounded
   metadata required to assist the owner.

The existing aggregate telephony analytics interface remains privacy-minimized and is
not repurposed as the recording archive.

## Appointment and arrangement engine

Ava appointment handling is a durable negotiation workflow:

1. create or attach to a work item;
2. resolve the contact/provider;
3. read calendar availability through a read-only adapter;
4. apply structured standing instructions and buffers;
5. prepare ranked acceptable time windows;
6. contact the external party through an approved communication channel;
7. record proposed slots and responses;
8. create/update the calendar event when policy allows;
9. attach confirmation details to the work item;
10. transition the work item to `scheduled` or `completed`.

The model never fabricates availability. Calendar writes must use a typed calendar
adapter with explicit attendee, time-zone, start/end, title and provenance fields.

## Cross-channel continuity

The office manager should link, not duplicate, authoritative data. For example:

- a telephone call creates `call:<opaque-id>` and `transcript:<opaque-id>` artifacts;
- the subsequent email is linked as `email_thread:<opaque-id>`;
- a calendar booking is linked as `calendar_event:<opaque-id>`;
- a return label remains in the authoritative document/archive system and is linked by
  a document reference;
- the work item holds only the orchestration state and bounded summary necessary to keep
  the matter moving.

## Action proposal lifecycle

Ava does not jump from language-model output to provider mutation.

`understand -> create/update work item -> propose typed action -> policy decision`

The policy decision is one of:

- `allowed` — the capability is within the configured authority class;
- `confirmation_required` — an owner decision is necessary;
- `blocked` — the office-manager path cannot execute it.

Even an `allowed` routine action is not executable while the global external execution
gate is disabled. An owner approval does not override a restricted or unknown
capability.

Future adapters will add an additional execution lifecycle:

`propose -> inspect -> validate -> authorize -> execute -> verify -> record -> rollback`

## Planned adapters

Each adapter gets its own schema, scopes, tests and commissioning gate.

### Calendar

- availability read;
- event prepare;
- create/update;
- cancel with confirmation;
- travel/buffer policy enforcement.

### Communications

- email/SMS correspondence read;
- draft preparation;
- routine send after explicit commissioning;
- follow-up tracking and reply correlation.

### Telephony

- recent-call and call-detail read;
- voicemail list/transcript read;
- streaming transcription;
- receptionist answer/session control;
- private consultation leg;
- attended transfer accept/decline/complete;
- bounded outbound origination for approved workflows.

### Contacts

- contact resolution;
- relationship/context projection;
- VIP and screening policy inputs.

### Purchasing/travel

- research and quote collection first;
- commitments remain conditional;
- payment, contract and financial-transfer authority stays outside this generic plane.

## Mobile and operator experience

The WW.CX admin UI should expose an Ava Office view with:

- work queue grouped by state;
- `Needs you` decisions;
- active/recent calls and transcript status;
- voicemail and callback queue;
- appointments being arranged;
- people waiting for a response;
- standing instructions;
- audit/provenance details;
- a daily briefing.

During an incoming warm transfer the mobile call card should emphasize a short briefing
plus large `Accept`, `Decline`, `Voicemail`, and `Ask Ava` actions.

## Commissioning sequence

1. **Foundation** — durable queue, authority policy, instructions, artifact links,
   audit chain. External execution disabled. **Implemented in this increment.**
2. **Read adapters** — calendar availability, detailed calls/voicemail, contacts and
   authorized communications projected into work items.
3. **Preparation adapters** — appointment proposals, communication drafts, callback
   plans and structured post-call tasks.
4. **Calendar routine execution** — typed create/update with rollback and verification.
5. **Attendant media plane** — recording, streaming transcription and receptionist
   session state, initially without external transfer/origination.
6. **Warm transfer** — attended transfer to an allowlisted owner destination with private
   consultation and accept/decline controls.
7. **Routine communications** — narrow outbound confirmations/follow-ups.
8. **Expanded office-manager workflows** — travel, purchasing and vendor coordination,
   each preserving its own approval gates.

Production call traffic, public routing changes, emergency calling, financial actions,
contracts/signatures, number porting and STIR/SHAKEN remain separate authorization
boundaries during commissioning.
