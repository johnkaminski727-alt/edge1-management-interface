# Cookie Monster Edge1 Foundation Installer

Status: source-ready deployment package; not applied to Edge1.

## Purpose

`deploy/cookie_monster_edge1_install.py` prepares the minimum private filesystem, service-account, disabled dataset-registry and hardened Fengus unit foundation required for a later non-production Cookie Monster Alpha activation.

The command is deliberately read-only unless `--apply` is supplied. Even in apply mode it does **not** enable `alpha-staging`, start a Fengus job, publish the cockpit, expose a listener, or change DNS, certificates, firewall, authentication, Apache routing, Big Bird mode, or canonical archive data.

## Default preflight

```bash
python3 deploy/cookie_monster_edge1_install.py
```

Preflight verifies:

- repository source exists at the selected root;
- the example dataset registry is still disabled, non-production and read-only;
- the registry does not carry path/URL/credential/command fields;
- the Fengus systemd unit retains `PrivateNetwork=yes`, `ProtectSystem=strict`, archive inaccessibility and the dedicated service user;
- whether the Fengus service account already exists;
- whether an existing runtime dataset registry conflicts with the disabled source example.

Preflight performs no filesystem, user or systemd mutation.

## Apply behavior

With an authenticated write-capable Edge1 path and a reviewed deployment window:

```bash
sudo python3 deploy/cookie_monster_edge1_install.py --apply
```

Apply is backup-first. It preserves the previous runtime registry and worker unit under a timestamped directory in `/var/backups`, including SHA-256 anchors. It refuses to overwrite an existing dataset registry that differs from the disabled source example.

It then prepares only this foundation:

```text
/etc/wwcx-cookie-monster/datasets.json                 disabled registry
/etc/systemd/system/cookie-monster-fengus-worker@.service
/srv/cookie-monster/datasets/alpha-staging            new directory mode 0555
/var/lib/cookie-monster-alpha/generated
/var/lib/cookie-monster-alpha/fengus/inbox
/var/lib/cookie-monster-alpha/fengus/outbox
cookie-monster-fengus                                  system nologin account
```

Existing directories are preserved without ownership/mode rewriting. New directories receive the narrow initial ownership/modes required for the foundation. `systemctl daemon-reload` is run, but no Fengus template instance is enabled or started.

The registry remains `enabled: false`. Populating and enabling `alpha-staging` is a later deliberate non-production activation step.

## Rollback

The apply output reports the backup directory. Configuration/unit rollback is explicit:

```bash
sudo python3 deploy/cookie_monster_edge1_install.py \
  --rollback /var/backups/wwcx-cookie-monster-alpha-foundation-<STAMP>-<PID>
```

Rollback verifies retained hashes and restores only the managed registry and systemd-unit state, followed by `systemctl daemon-reload`.

It intentionally **does not delete** runtime directories or a newly-created Fengus account. That preserves staged/evidence data and stable numeric ownership rather than turning rollback into a destructive cleanup operation.

## Validation

Source validation:

```bash
python3 -m py_compile deploy/cookie_monster_edge1_install.py tests/test_cookie_monster_edge1_install.py
python3 -m unittest -v tests.test_cookie_monster_edge1_install
```

The regression suite covers read-only preflight, disabled/non-production/read-only registry enforcement, rejection of authority-bearing registry fields, required worker hardening, registry-conflict reporting, root gating for apply, and root gating for rollback.

## Current execution boundary

The currently exposed Edge1 Operator connector is read-only. Therefore this package can be reviewed, tested and merged, but a live `--apply` cannot truthfully be claimed until an authenticated write-capable Edge1 execution path is available. Source readiness is not runtime activation.
