# WW.CX Unified Communications workspace

Date: 2026-08-18

## Purpose

`/communications/` is now a daily operator workspace rather than only a channel launcher. It presents a chronological canonical-event timeline while preserving Mail Room, Messaging Operations, Voice/SIP, and News/Relay as specialist tools.

## Read-only API

`server/unified_communications_server.py` binds only to loopback and serves:

- `GET /communications/healthz`
- `GET /communications/api/v1/readiness`
- `GET /communications/api/v1/events`
- `GET /communications/api/v1/events/{communications_event_id}`
- static workspace assets

POST, PUT, PATCH, and DELETE return `405 read_only_workspace` with `mutation_authorized: false`.

The API reads only an operator-supplied canonical JSONL snapshot. Each event must pass `wwcx.communications-event.v1` validation before it can enter the timeline. The snapshot is capped at 32 MiB and the API returns at most 500 events per query.

Search is restricted to the canonical metadata allowlist. Raw bodies, raw audio, attachment bytes, credentials, secrets, tokens, and permission-bearing retrieved fields are rejected by the core contract layer.

## Operator UX

The workspace includes:

- All activity, Inbox, Drafts, Sent/submitted, Quarantine, and Needs-attention views;
- All/Mail/SMS/MMS/Voice/SIP/News/Relay channel filters;
- metadata search;
- chronological event timeline;
- details inspector for identity, case, channel, security, delivery state, AI derivation, native source/provider ID, and audit references;
- a channel-by-channel readiness matrix;
- direct links to the specialist channel tools.

An unavailable API or empty snapshot is shown as unavailable/empty; the UI does not fabricate activity.

## Provenance and authority

Every rendered event remains a reference to an authoritative native channel record. The workspace does not replace the native Mail, Messaging, Voice/SIP, or Relay stores.

The workspace is not a send/control plane. No provider adapter, telephony origination, carrier route, mail submission, messaging submission, quarantine release, generic shell, or configuration mutation endpoint exists here.

## Deployment boundary

This increment is repository-ready only. Deploying or reverse-proxying the loopback workspace on Edge1 is a separate runtime action. Fresh live acceptance must verify the loopback listener, authenticated proxy boundary if used, canonical snapshot source, content provenance, UI route, and rollback path.
