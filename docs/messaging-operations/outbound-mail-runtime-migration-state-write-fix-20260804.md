# Outbound-mail runtime migration state-write fix

Date: 2026-08-04

## Live failure evidence

The first authorized safe-disabled runtime migration attempt on Edge1 reached the new runtime entrypoint and passed these checks:

- service active on loopback port 8104;
- health returned HTTP 200;
- status returned HTTP 200;
- unsigned authenticated status returned HTTP 401;
- external delivery and policy remained disabled;
- no provider was ready and no sender was live.

The disabled send probe returned HTTP 500 with `unable to open database file` instead of the required HTTP 403. The installer then executed its automatic rollback. The prior gateway recovered active, the original source configuration SHA-256 remained unchanged, and no provider credential, sender, delivery gate, message preparation, or mail traffic was enabled.

## Root cause

The hardened base unit uses `ProtectSystem=strict` and permits writes only to the repository-relative state directory. The runtime migration moved SQLite state to:

```text
/var/lib/wwcx-outbound-mail
```

but its generated systemd drop-in changed only `ExecStart`. The service could read its runtime configuration but could not create SQLite journal files in the new state root.

## Bounded correction

The repair wrapper is:

```text
deploy/messaging/install-outbound-mail-disabled-runtime-migration-fixed.sh
```

It does not replace or weaken the audited installer. It creates a private temporary copy and injects exactly one line into the installer's single systemd service drop-in template:

```text
ReadWritePaths=$STATE_ROOT
```

The temporary script is syntax-checked and then executed. All original controls remain authoritative, including:

- root and host checks;
- clean `main` and exact `EXPECTED_COMMIT` gate;
- explicit `RUNTIME_MIGRATION_AUTHORIZED=yes` gate;
- safe-disabled configuration checks;
- dedicated non-root service account;
- loopback-only listener checks;
- source configuration hash preservation;
- post-install HTTP 200, 401, and disabled-send 403 checks;
- automatic rollback.

The wrapper refuses an unexpected number of `[Service]` template blocks and refuses to run when the original installer already contains the write boundary.

## Preserved boundaries

This fix does not read credentials or secrets, change DNS or firewall rules, add a public listener, enable a provider or sender, enable external delivery, prepare a production message, or send mail.

The live retry remains a separately controlled production service-entrypoint operation and must use the exact merged commit.
