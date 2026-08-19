---
name: shared-host-security-auditor
description: Perform read-mostly security audits of Business159 and future WW.CX shared-host accounts using bounded account-level inspection. Use to check public backups/archives, .env or secret-file exposure, suspicious executables, world-writable or unexpected permissions, stale PHP, dangerous routing, public/private boundary violations, HTTPS/certificate problems, and repository/deployment drift while never printing discovered secrets.
---

# Shared Host Security Auditor

Audit before remediation. Prefer `business159.*` read-only tools and `business159_inspect`; use guarded shell only when a specific gap cannot be checked otherwise.

Check, where accessible:

- backups, archives, dumps, private/config files accidentally under webroots;
- `.env`, keys, token/cookie/session material, and secret-bearing files without printing their contents;
- unexpected executable PHP/scripts and stale/orphaned entrypoints;
- world-writable or anomalous ownership/modes;
- dangerous `.htaccess`/routing or public/private boundary changes;
- HTTPS/TLS failures;
- source/deployment drift and unexpected dirty state;
- deployment artifacts left public.

Report only safe metadata such as path, type, mode, size, mtime, hash/fingerprint, relationship, and finding category. For secret-bearing discoveries, state presence/risk and redact the value completely.

Do not broaden permissions to inspect something. Do not remediate automatically when the fix changes authentication, DNS/TLS, public exposure, or unrelated customer data. For an obviously safe bounded repair already covered by the active task, use the authenticated/filesystem workflow with backup and verification.
