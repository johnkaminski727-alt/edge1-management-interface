# Unified Communications — Phase 27 Validation Record

Date: 2026-08-18
Base main at branch creation: `967096132bc5f998d68893ff43c81ffc3f37e2b5`
Branch: `agent/unified-communications-phase27-20260818`
Scope: repository implementation and bounded validation only; live Edge1 acceptance not executed in this session

## Repository implementation

Phase 27 adds the remaining repository-side foundations without claiming runtime completion:

1. **MMS trusted scanner adapter**
   - `services/wwcx-messaging-gateway/app/trusted_scanner.py`
   - fixed executable `/usr/bin/clamscan`;
   - fixed non-destructive options only;
   - no caller-controlled executable or option vector;
   - no cloud or third-party upload;
   - no `clamd` listener requirement;
   - exit code `0` -> clean, `1` -> malicious, all other statuses fail closed as unavailable;
   - subprocess timeout becomes a held timeout through the existing `scan_stored_media` boundary.

2. **MMS local synthetic acceptance probe**
   - `services/wwcx-messaging-gateway/scripts/private-quarantine-acceptance.py`
   - uses only locally generated clean and EICAR artifacts;
   - no provider/carrier traffic;
   - clean must remain `scanned_clean_held`;
   - EICAR must remain `quarantined_malicious`;
   - restart/re-open must preserve held state;
   - release remains false.

3. **Mail private correspondence store foundation**
   - `server/mail_correspondence_store.py`
   - private SQLite parent `0700`, database `0600`;
   - canonical Message-ID validation;
   - explicit thread IDs and preserved provider message/thread IDs;
   - bounded subject/body/provider IDs/results;
   - explicit source provenance including `authoritative` boolean;
   - message bodies always returned with `content_is_untrusted=true`;
   - `mutation_authorized=false` and `send_authorized=false`;
   - no network or provider code.

4. **Mail synthetic validation**
   - `tests/validate_mail_correspondence_store.py`
   - validates persistence, thread ordering, provenance, explicit reply linkage, size bounds, duplicate/malformed-ID failure, private permissions, and prompt-like body non-authority.

5. **Runtime acceptance procedure**
   - `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md`
   - separates repository readiness from Edge1 scanner/root deployment and native Mail source authorization.

## Source audit conclusion

The repository still does not contain an authoritative persisted native Mail Room body/thread-history source. `server/mail_threading.py` provides explicit correlation metadata; `server/inbound_mail_hub.py` provides disabled-by-default routing/audit behavior; `config/messaging/inbound-mail-hub.json` has raw-message, attachment-byte, and body-preview persistence disabled. Provider inventory also does not prove the canonical provider-side mailboxes are provisioned.

Therefore `mail.correspondence.read` remains blocked for production/native correspondence until an explicitly authorized mailbox/MTA source is connected. Synthetic validation proves only the local storage/read contract.

## Runtime execution-path blocker

This ChatGPT session did not expose the Edge1 Live Shell connector or another authenticated Edge1 execution connector. The execution container had no SSH agent and no local SSH identity. Consequently:

- no Edge1 package installation was attempted;
- no claim is made that `/usr/bin/clamscan` exists live;
- no live private quarantine root was created;
- no Messaging service was restarted;
- no live synthetic MMS acceptance was executed;
- no live Mail source/store integration was executed.

This is an execution-path blocker, not a repository implementation failure.

## Readiness interpretation

Until live acceptance exists:

- `fresh_edge1_runtime_verified` remains `false`;
- SMS/MMS `security_quarantine` remains `degraded` even though the concrete scanner adapter is repository-ready;
- Mail `mail.correspondence.read` remains intentionally disabled/blocked;
- live carrier readiness, provider credentials, DNS readiness, mail delivery readiness, emergency calling, and quarantine release are unchanged and not implied.

## Required CI

Exact-head pull-request CI must include at minimum:

- WW.CX Messaging Gateway unit tests and compile validation;
- repository validation covering `tests/validate_mail_correspondence_store.py` or an equivalent explicit invocation;
- relevant repository/Edge1 Operator validation workflows triggered by the changed files.

Green CI is repository evidence only and is not live Edge1 acceptance.
