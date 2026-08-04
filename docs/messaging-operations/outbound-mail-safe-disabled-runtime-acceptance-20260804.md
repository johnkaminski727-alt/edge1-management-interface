# Safe-disabled outbound-mail runtime acceptance

Date: 2026-08-04

## Accepted live state

The disabled outbound-mail runtime migration completed successfully on `edge1.ww.cx` from clean `main` at exact commit:

```text
1f79d030bec94c6247e3fb5bc93a7f6a76d65ad6
```

The accepted operator evidence records:

- audit evidence: `/var/lib/wwcx-deployment-evidence/outbound-mail-runtime-migration/20260804T051426Z`;
- install evidence: `/var/lib/wwcx-deployment-evidence/outbound-mail-runtime-migration/20260804T051435Z`;
- service: `wwcx-outbound-mail-gateway.service`;
- loopback listener: `127.0.0.1:8104`;
- runtime state: `runtime_migration_active_safe_disabled`;
- state root and systemd write boundary: `/var/lib/wwcx-outbound-mail`;
- audit failures: `0`;
- install failures: `0`;
- rollback executed: `no`;
- original preparation configuration preserved: `yes`.

The accepted minimized machine-readable record is:

```text
records/messaging/deployment-evidence/outbound-mail-safe-disabled-runtime-acceptance-20260804.json
```

## Post-fix verification

After PR #293 merged the Git-index ownership fix, Edge1 fast-forwarded clean `main` to:

```text
681806b1190e0639d12120566fa8733430fd3fae
```

The operator then ran the non-mutating `ACTION=verify` path. Accepted results:

- verification captured at `2026-08-04T05:33:16Z`;
- verification evidence: `/var/lib/wwcx-deployment-evidence/outbound-mail-runtime-migration/20260804T053316Z`;
- readiness remained `runtime_migration_active_safe_disabled`;
- verification failures: `0`;
- source configuration SHA-256 remained unchanged;
- `.git/index` remained owned by `wwadmin:wwadmin` with mode `0644` after the root verification;
- the repository worktree remained clean.

The reviewed wrapper now runs the root-level installer with `GIT_OPTIONAL_LOCKS=0`. This preserves the installer's exact-commit and clean-main checks while preventing an optional Git index refresh from rewriting the operator-owned index as root.

## What this resolves

The live runtime now uses the strict `/etc/wwcx` configuration root and `/var/lib/wwcx-outbound-mail` state root. The systemd sandbox admits the exact state root required for SQLite audit, nonce, delivery-event, and suppression state. The installer completed all of its safe-disabled functional checks.

This removes only the Phase E blocker that the safe-disabled runtime migration had not yet been executed. The post-fix verification also closes the repository-ownership regression introduced by the root-level audit path.

## Preserved boundaries

The accepted deployment and verification did not:

- read an HMAC secret or provider credential;
- enable a provider, policy, sender, send endpoint, or external delivery;
- prepare or send a message;
- modify DNS, firewall, certificates, Apache, or public listeners;
- overwrite the original preparation configuration;
- rerun the installer or restart the gateway during the post-fix verification.

The source configuration SHA-256 remained:

```text
b82b6e9c74245d40ce4eb467bbd9aee4006a9b3db0538a5df8801f0764485db4
```

## Remaining Phase E gates

The runtime remains intentionally safe-disabled. Separate explicit authorization and accepted evidence are still required for:

- an approved organization mailing address;
- secure provider credential installation;
- the authentication-only SMTP canary;
- exact provider and sender capability verification;
- return-path, bounce, complaint, and suppression operations;
- monitoring DMARC publication;
- one exact owned-recipient pilot payload;
- any provider, sender, policy, send-endpoint, or external-delivery activation.

A generic continuation does not authorize these actions or any production message traffic.

## Verification

Run the repository-only validator with:

```sh
python3 tests/validate_outbound_mail_runtime_acceptance_record.py
```

The validator rejects secret-bearing keys, PEM material, email addresses, changed safety gates, malformed evidence paths, unexpected commit or source hashes, repository-ownership drift, and any claim that an independent evidence-manifest recheck was recorded when it was not shown in the accepted operator transcript.
