# Edge1 Suricata updater runtime repair — 2026-08-18

## Incident evidence

Fresh authenticated Edge1 inspection found two simultaneous Suricata runtimes on `wg0`:

- accepted managed sensor: `wwcx-network-sensor-suricata.service`, libpcap capture, enabled and active;
- legacy runtime: `suricata.service`, AF_PACKET capture, disabled but active.

The host had approximately 3.8 GiB RAM, 1.0 GiB swap fully consumed, and repeated OOM kills during the scheduled rules update window. The live `wwcx-suricata-update.service` still declared `Requires=suricata.service`, while `/usr/local/sbin/wwcx-suricata-update` inspected that legacy unit and used `suricatasc` against its command socket. This dependency could start the disabled legacy daemon whenever the timer ran.

The incident journal showed the legacy live reload beginning at 04:32:03 UTC and the legacy process being OOM-killed at 04:35:57 UTC. A successful reload request therefore cannot be treated as immediate acceptance.

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
- optional `WWCX_SURICATA_UPDATE_VALIDATE_ONLY=1` mode performs download/validation without installing rules or reloading the live daemon;
- changed-rule reloads use a default 300-second stability observation window and fail/restore if the managed service becomes inactive, its PID changes, or its restart counter changes during that window.

The base service intentionally does not define `ExecStartPost`; Edge1 already has a retention drop-in for `/usr/local/sbin/wwcx-suricata-rule-backup-prune`, which must remain singular.

## Guarded live repair

The repair transaction requires root, Edge1 host identity, an active/enabled managed sensor, an already active/enabled update timer, and either:

- clean `main` containing the exact reviewed repair commit; or
- a clean detached worktree whose `HEAD` is exactly the reviewed repair commit.

The detached-worktree path permits a bounded repair without fast-forwarding the materially older production checkout.

The repair transaction:

1. records service/process/memory state and SHA-256 evidence;
2. verifies the existing retention drop-in/helper before mutation;
3. backs up the live updater, update service and timer;
4. installs only those three reviewed artifacts;
5. reloads systemd without restarting the managed sensor and without starting/restarting the persistent timer;
6. disables/stops the duplicate legacy `suricata.service` only after the new dependency contract is loaded;
7. verifies exactly one `/usr/bin/suricata` runtime remains and that it is the managed libpcap sensor;
8. verifies the loaded update service requires the managed sensor and no longer requires the legacy unit;
9. verifies the retention `ExecStartPost` remains present exactly once;
10. records post-repair memory/service/process evidence and only then clears the historical failed state of the update oneshot;
11. preserves rollback evidence and restores prior updater/unit files plus the prior legacy-service state on failure.

No firewall, DNS, WireGuard, routing, certificate, authentication, production traffic or packet-filter policy change is part of this repair.

## First live repair attempt — guard correction

The first bounded live attempt correctly installed the managed updater artifacts and stopped/disabled the duplicate legacy runtime, but then reported `loaded update unit still requires legacy Suricata` even though `systemctl show` contained only `wwcx-network-sensor-suricata.service` plus ordinary system dependencies.

Two repair-script defects were identified from that live evidence:

1. the dependency guard used substring matching, so `suricata.service` falsely matched the suffix of `wwcx-network-sensor-suricata.service`;
2. `fail()` used `exit 1`, which bypassed the intended rollback path after mutation and therefore left no `result.txt` or failure evidence record.

The corrected contract treats systemd dependency lists as exact whitespace-delimited unit tokens and explicitly invokes rollback when `fail()` is called after `MUTATION_STARTED=true`. Regression validation forbids the old substring check and requires exact-token matching plus the explicit rollback path.

The resulting live state after the guarded abort was nevertheless the intended runtime shape: legacy `suricata.service` inactive/disabled, managed `wwcx-network-sensor-suricata.service` active/enabled as the sole Suricata runtime, update timer active/enabled, and available memory increased from roughly 366 MiB before the attempt to roughly 1.5 GiB afterward. This state still requires a corrected formal acceptance run before the repair is labelled complete.

## Deployment sequencing

Because the live repository checkout is materially behind current `main`, do not combine this repair with an unrelated bulk fast-forward. After merge, fetch the exact repair commit, create a detached temporary worktree for that commit, run the guarded repair from that worktree with `EXPECTED_COMMIT` pinned, capture acceptance evidence, and remove only the temporary worktree after success. Then separately plan repository reconciliation and MCP deployment.
