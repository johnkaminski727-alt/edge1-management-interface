# Ava protected call archive read adapter

Date: 2026-08-23
Status: HTTP source integrated; not live-activated

## Purpose

Provide Ava Office with a bounded read-only model for recent call metadata, voicemail discovery, and transcript retrieval without weakening the privacy-minimized telephony analytics boundary.

The aggregate telephony APIs remain appropriate for health, counts, summaries, interconnect state, and anomalies. Caller-level records and transcript text belong in a separate protected owner-facing archive.

## Layout contract

The adapter consumes only files under one configured root:

```text
<root>/
  manifests/<call_ref>.json
  transcripts/<transcript_ref>.txt
```

Call manifests follow `schemas/ava/call-record.schema.json`. The adapter never accepts a caller-supplied path. `call_ref` and `transcript_ref` are validated opaque references and are resolved into the fixed subdirectories above.

Default runtime root:

```text
/var/lib/wwcx-ava-office-manager/call-archive
```

This path is already inside the Ava Office service's existing read-only data boundary. Activation must not broaden the service to PBX configuration, call control, carrier routing, or arbitrary filesystem access.

## Read behavior

`AvaCallArchiveReadModel` provides:

- `health()` — archive availability and manifest count;
- `calls(limit=...)` — recent call metadata, ordered newest first;
- `voicemails(limit=...)` — recent calls containing a voicemail segment;
- `transcript(call_ref, max_chars=...)` — bounded UTF-8 transcript text for one validated call reference.

Call-list results intentionally omit transcript text, recording references, audio references, and integrity hashes. They expose only bounded owner-facing call metadata such as call reference, timestamps, direction, contact references, disposition, and booleans indicating voicemail/recording/transcript/summary availability.

Transcript reads:

- never read audio;
- are capped at 1 MiB on disk and 100,000 returned characters;
- verify `transcript_sha256` when the manifest provides it;
- fail closed on a digest mismatch;
- return `audio_exposed=false` and privacy class `protected_evidence`.

## Ava Office HTTP source contract

`server/ava_office_manager_server.py` wires the model into the existing loopback-only Ava Office GET surface:

```text
GET /api/ava-office/call-archive/health
GET /api/ava-office/calls?limit=50
GET /api/ava-office/voicemails?limit=50
GET /api/ava-office/transcript?call_ref=<opaque-ref>&max_chars=20000
```

The normal `/healthz` response includes the call-archive availability as a nested component without making absence of a not-yet-provisioned archive fatal to the Office read API itself.

POST, PUT, PATCH and DELETE remain blocked with HTTP 405 by the same read-only handler used for all Ava Office endpoints. Transcript retrieval is explicit per call reference; call-list and voicemail-list endpoints never inline transcript bodies.

The immutable commissioning script packages and hashes `ava_call_archive.py` with the Office server and store module so a future runtime cannot start an API that imports a module missing from the pinned release.

## Safety boundaries

This source does **not**:

- answer or originate calls;
- bridge or transfer calls;
- change Asterisk/FreePBX/PJSIP configuration;
- alter recording or transcription policy;
- create, edit, or delete call records;
- expose PBX credentials or call-control sockets;
- create a public listener;
- make transcript content part of aggregate status snapshots.

Live call handling, recording activation, warm transfers, carrier routing, and emergency-path behavior remain separate explicitly gated work.

## Remaining activation sequence

The read model, loopback HTTP routes, immutable runtime packaging, and regression tests are source-complete. Before representing recent calls, voicemail, or transcript retrieval as live:

1. establish the protected archive writer and retention policy;
2. prove produced manifests conform to the call-record schema;
3. prove transcript refs and hashes are produced consistently;
4. commission an exact reviewed Ava Office runtime and verify 127.0.0.1:8116 only;
5. exercise the call/voicemail/transcript GET endpoints against protected test records;
6. verify all mutation methods remain 405 and audio is never returned;
7. connect Private AI only through an explicit telephony/call-history read scope.

Until those steps are accepted, this implementation is source-ready only and must not be represented as live voicemail or transcript access.
