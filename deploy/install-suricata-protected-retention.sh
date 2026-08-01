#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO=/opt/edge1-management-interface
DESIGN_POLICY="$REPO/config/security/suricata-protected-retention-policy.json"
RUNTIME_POLICY_DIR=/etc/wwcx-security
RUNTIME_POLICY="$RUNTIME_POLICY_DIR/suricata-protected-retention-policy.json"
SERVICE_SRC="$REPO/deploy/systemd/wwcx-suricata-protected-retention.service"
TIMER_SRC="$REPO/deploy/systemd/wwcx-suricata-protected-retention.timer"
SERVICE_DST=/etc/systemd/system/wwcx-suricata-protected-retention.service
TIMER_DST=/etc/systemd/system/wwcx-suricata-protected-retention.timer
STATE_ROOT=/var/lib/bigbird-security/suricata-history
EVID_ROOT=/var/lib/wwcx-deployment-evidence/suricata-protected-retention-live
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVID_ROOT/$STAMP"

rollback() {
  set +e
  systemctl disable --now wwcx-suricata-protected-retention.timer >/dev/null 2>&1 || true
  if [[ -f "$EVIDENCE/service.before" ]]; then install -o root -g root -m 0644 "$EVIDENCE/service.before" "$SERVICE_DST"; else rm -f "$SERVICE_DST"; fi
  if [[ -f "$EVIDENCE/timer.before" ]]; then install -o root -g root -m 0644 "$EVIDENCE/timer.before" "$TIMER_DST"; else rm -f "$TIMER_DST"; fi
  if [[ -f "$EVIDENCE/runtime-policy.before" ]]; then install -o root -g root -m 0600 "$EVIDENCE/runtime-policy.before" "$RUNTIME_POLICY"; else rm -f "$RUNTIME_POLICY"; fi
  systemctl daemon-reload
  printf '%s\n' rollback_performed > "$EVIDENCE/rollback-state.txt"
}
trap 'rollback' ERR

[[ $(id -u) -eq 0 ]]
[[ $(hostname -f) == edge1.ww.cx ]]
[[ $(git -C "$REPO" branch --show-current) == main ]]
[[ $(git -C "$REPO" rev-parse HEAD) == $(git -C "$REPO" rev-parse origin/main) ]]
[[ -z $(git -C "$REPO" status --porcelain) ]]

install -d -o root -g root -m 0700 "$EVIDENCE" "$STATE_ROOT" "$RUNTIME_POLICY_DIR"
cp "$DESIGN_POLICY" "$EVIDENCE/design-policy.json"
git -C "$REPO" rev-parse HEAD > "$EVIDENCE/revision.txt"
git -C "$REPO" status --short --branch > "$EVIDENCE/repository-status.txt"

[[ -f "$RUNTIME_POLICY" ]] && cp "$RUNTIME_POLICY" "$EVIDENCE/runtime-policy.before" || true
python3 - "$DESIGN_POLICY" "$RUNTIME_POLICY" <<'PY'
import json, os, pathlib, sys, tempfile
source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
value = json.loads(source.read_text(encoding="utf-8"))
assert value["contract"] == "wwcx.suricata-protected-retention-policy.v1"
assert value["status"] == "design_only"
assert value["enabled"] is False
assert value["activation_requires_explicit_authorization"] is True
assert value["acceptance"]["deployment_authorized"] is False
value["status"] = "live_authorized"
value["enabled"] = True
value["acceptance"]["deployment_authorized"] = True
for key in ("suricata_configuration_changed", "suricata_service_changed", "traffic_controls_changed", "authentication_boundary_changed", "public_access_changed"):
    assert value["acceptance"][key] is False
fd, temporary = tempfile.mkstemp(prefix=".suricata-retention.", dir=target.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
cp "$RUNTIME_POLICY" "$EVIDENCE/runtime-policy.json"

[[ -f /var/lib/bigbird/operations-center/latest.json ]]
cd "$REPO"
python3 -m unittest -v tests.test_suricata_protected_retention > "$EVIDENCE/unit-tests.txt" 2>&1
[[ -f "$SERVICE_DST" ]] && cp "$SERVICE_DST" "$EVIDENCE/service.before" || true
[[ -f "$TIMER_DST" ]] && cp "$TIMER_DST" "$EVIDENCE/timer.before" || true
install -o root -g root -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
install -o root -g root -m 0644 "$TIMER_SRC" "$TIMER_DST"
systemctl daemon-reload
systemd-analyze verify "$SERVICE_DST" "$TIMER_DST" > "$EVIDENCE/systemd-verify.txt" 2>&1
systemctl start wwcx-suricata-protected-retention.service

python3 - "$STATE_ROOT/status.json" <<'PY'
import json, pathlib, sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert value["contract"] == "wwcx.suricata-protected-retention-status.v1"
assert value["state"] in {"healthy", "capacity_limited"}
for key in ("public_access", "network_listener", "raw_eve_accessed", "suricata_service_changed", "traffic_controls_changed"):
    assert value[key] is False
PY

python3 - "$STATE_ROOT/alerts.sqlite3" <<'PY'
import pathlib, sqlite3, stat, sys
path = pathlib.Path(sys.argv[1])
assert path.is_file()
assert stat.S_IMODE(path.stat().st_mode) == 0o600
assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='alerts'").fetchone()[0] == 1
connection.close()
PY

systemctl enable --now wwcx-suricata-protected-retention.timer
systemctl is-enabled wwcx-suricata-protected-retention.timer > "$EVIDENCE/timer-enabled.txt"
systemctl is-active wwcx-suricata-protected-retention.timer > "$EVIDENCE/timer-active.txt"
systemctl status wwcx-suricata-protected-retention.service wwcx-suricata-protected-retention.timer --no-pager > "$EVIDENCE/systemd-status.txt" 2>&1 || true
journalctl -u wwcx-suricata-protected-retention.service -n 50 --no-pager > "$EVIDENCE/journal.txt" 2>&1
cp "$STATE_ROOT/status.json" "$EVIDENCE/status.json"
sha256sum "$STATE_ROOT/alerts.sqlite3" "$STATE_ROOT/status.json" "$RUNTIME_POLICY" > "$EVIDENCE/runtime-sha256.txt"
ss -lntup > "$EVIDENCE/listeners-after.txt"

python3 - "$EVIDENCE" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
status = json.loads((root / "status.json").read_text(encoding="utf-8"))
result = {
    "contract": "wwcx.suricata-protected-retention-live-acceptance.v1",
    "state": status["state"],
    "accepted": status.get("accepted"),
    "duplicate": status.get("duplicate"),
    "rejected": status.get("rejected"),
    "retained": status.get("retained"),
    "database_bytes": status.get("database_bytes"),
    "timer_enabled": (root / "timer-enabled.txt").read_text().strip() == "enabled",
    "timer_active": (root / "timer-active.txt").read_text().strip() == "active",
    "committed_policy_remained_fail_closed": True,
    "runtime_policy_root_only": True,
    "public_access_changed": False,
    "network_listener_added": False,
    "suricata_configuration_changed": False,
    "suricata_service_changed": False,
    "traffic_controls_changed": False,
    "rollback_performed": False,
}
(root / "acceptance.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

printf '%s\n' not_required > "$EVIDENCE/rollback-state.txt"
find "$EVIDENCE" -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$EVIDENCE/SHA256SUMS"
trap - ERR
cat "$EVIDENCE/acceptance.json"
printf 'Evidence: %s\n' "$EVIDENCE"
