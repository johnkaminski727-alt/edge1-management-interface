# Edge1 Suricata updater runtime repair — 2026-08-18

## Incident evidence

Fresh authenticated Edge1 inspection found two simultaneous Suricata runtimes on `wg0`:

- accepted managed sensor: `wwcx-network-sensor-suricata.service`, libpcap capture, enabled and active;
- legacy runtime: `suricata.service`, AF_PACKET capture, disabled but active.

The host had approximately 3.8 GiB RAM, 1.0 GiB swap fully consumed, and repeated OOM kills during the scheduled rules update window. The live `wwcx-suricata-update.service` still declared `Requires=suricata.service`, while `/usr/local/sbin/wwcx-suricata-update` inspected that legacy unit and used `suricatasc` against its command socket. This dependency could start the disabled legacy daemon whenever the timer ran.

The accepted managed sensor already exposes `ExecReload=+/bin/kill -USR2 $MAINPID` and intentionally disables the Unix command socket. Therefore the correct update boundary is systemd reload of `wwcx-network-sensor-suricata.service`, not `suricatasc` and not the retired `suricata.service`.

## Repair contract

Repository-owned repair artifacts:

- `deploy/security/wwcx-suricata-update`
- `deploy/systemd/wwcx-suricata-update.service`
- `deploy/systemd/wwcx-suricata-update.timer`
- `deploy/repair-edge1-suricata-update-runtime.sh`
- `tests/validate_suricata_update_runtime_repair.py`

The updater preserves the existing candidate-download, offline validation, SHA-256 comparison, backup, atomic replacement, restoration, backup-retention and PID/restart verification behavior. It changes only runtime ownership:

- managed service default: `wwcx-network-sensor-suricata.service`;
- managed sensor environment from `/etc/default/wwcx-network-sensor`;
- candidate validation uses the configured capture argument rather than hard-coded AF_PACKET;
- live reload uses `systemctl reload` and therefore the reviewed SIGUSR2 unit contract;
- explicit refusal to target `suricata.service`;
- optional `WWCX_SURICATA_UPDATE_VALIDATE_ONLY=1` mode performs download/validation without installing rules or reloading the live daemon.

The base service intentionally does not define `ExecStartPost`; Edge1 already has a retention drop-in for `/usr/local/sbin/wwcx-suricata-rule-backup-prune`, which must remain singular.

## Guarded live repair

The repair transaction requires root, Edge1 host identity, a clean `main` checkout containing the exact reviewed commit, and an active/enabled managed sensor. It:

1. records service/process state and SHA-256 evidence;
2. backs up the live updater, update service and timer;
3. installs only those three reviewed artifacts;
4. reloads systemd without restarting the managed sensor;
5. keeps the existing update timer enabled/active;
6. resets only the failed update-service state;
7. disables/stops the duplicate legacy `suricata.service`;
8. verifies exactly one remaining Suricata main process and that it is the managed libpcap sensor;
9. verifies the loaded update service requires the managed sensor and no longer requires the legacy unit;
10. preserves rollback evidence and restores prior files/service states on failure.

No firewall, DNS, WireGuard, routing, certificate, authentication, production traffic or packet-filter policy change is part of this repair.

## Deployment sequencing

Because the live repository checkout is materially behind current `main`, do not combine this repair with an unrelated bulk fast-forward. Deploy from the exact reviewed repair commit using a bounded staging/backup procedure, validate the managed sensor and memory state, then separately plan repository reconciliation and MCP deployment.
