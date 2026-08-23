# Ava protected call archive write and retention contract

Date: 2026-08-23
Status: source foundation; not live-activated

## Purpose

Define one auditable destination for Ava call transcripts and call-record manifests without granting the archive writer PBX control, audio access, deletion authority, or public network exposure.

This writer complements the read-only adapter in `server/ava_call_archive.py`. It does not activate recording or transcription and does not decide whether a call may be recorded. Those decisions remain in the attendant/media policy and production call-control boundary.

## Archive layout

The fixed-root archive is:

```text
<root>/
  journals/<call_ref>.jsonl
  manifests/<call_ref>.json
  transcripts/<transcript_ref>.txt
```

Recommended runtime root:

```text
/var/lib/wwcx-ava-office-manager/call-archive
```

All references are opaque validated identifiers. Caller-supplied filesystem paths are never accepted.

## Streaming journal

`AvaCallArchiveWriter.append_transcript_event()` appends bounded UTF-8 transcript events to the call journal. Each event contains only:

- schema version;
- call reference;
- event reference;
- RFC 3339 UTC timestamp;
- bounded speaker role (`caller`, `ava`, `owner`, or `system`);
- bounded transcript text.

The journal is append-only and is preserved after finalization. Duplicate event references cause finalization to fail closed. Journals are capped at 4 MiB and 4096 events per call.

## Finalization

`finalize_call()` publishes immutable final objects. It:

1. validates the call reference, timestamp, direction, media-policy shape, notice state, and consent state;
2. requires a recorded `notice` event when the media policy says notice is required;
3. refuses media finalization when required consent is not `granted`;
4. renders the transcript only from the append-only transcript journal;
5. computes the transcript SHA-256;
6. requires a supplied recording SHA-256 when a recording reference is present, but never opens or copies recording audio;
7. computes the manifest SHA-256 over canonical JSON with `integrity.manifest_sha256` omitted;
8. creates final transcript and manifest files with create-only semantics and mode `0600`;
9. refuses to replace an existing final object.

The read adapter independently recomputes and verifies the same canonical manifest hash before returning a call record, and verifies transcript hashes before returning transcript text.

## Crash and orphan behavior

The writer favors evidence preservation over cleanup. If a transcript has been published but manifest publication fails, the transcript is intentionally left in place for reconciliation rather than deleted automatically.

A reconciliation tool may identify orphaned objects later, but deletion or destructive retention enforcement must be a separately authorized operation.

## Retention rule

**No automatic deletion is permitted by this writer.**

The writer exposes no delete, purge, truncate, overwrite, or retention-expiry method. Retention policy may classify records and calculate future review dates, but actual destruction must be handled by a separate audited workflow with explicit policy and authorization.

This prevents a misconfigured retention interval from silently destroying call evidence.

## Explicit non-capabilities

The writer does not:

- answer, originate, bridge, transfer, hold, or terminate calls;
- connect to AMI, ARI, Asterisk CLI, FreePBX, PJSIP, SIP trunks, or carrier APIs;
- start or stop recording or transcription;
- determine legal notice or consent requirements;
- read or copy audio;
- expose caller records through the aggregate telephony analytics API;
- create a listener or accept network requests;
- delete archived evidence;
- send messages, notifications, or external communications.

## Activation sequence

Before this writer is used in production:

1. identify the exact production transcription event producer;
2. prove that producer supplies notice/consent state from the accepted attendant policy;
3. establish the root-owned/least-privilege archive directory and writer identity;
4. add a narrow local handoff contract from the transcription producer to the writer;
5. commission the existing Ava Office read API separately and verify loopback-only behavior;
6. run synthetic and attended acceptance without live external call traffic first;
7. only then consider production call recording/transcription activation under its separate authorization boundary.

Source availability must never be represented as live recording, voicemail transcription, or call-control capability until those runtime acceptance steps have passed.
