#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

REPO=/opt/edge1-management-interface
DESIGN_POLICY="$REPO/config/security/edge1-public-summary-staging-policy.json"
RUNTIME_POLICY_DIR=/etc/wwcx-security
RUNTIME_POLICY="$RUNTIME_POLICY_DIR/edge1-public-summary-staging-policy.json"
SERVICE_SRC="$REPO/deploy/systemd/wwcx-edge1-public-summary-stager.service"
TIMER_SRC="$REPO/deploy/systemd/wwcx-edge1-public-summary-stager.timer"
SERVICE_DST=/etc/systemd/system/wwcx-edge1-public-summary-stager.service
TIMER_DST=/etc/systemd/system/wwcx-edge1-public-summary-stager.timer
STAGING_ROOT=/var/lib/wwcx-public-summary
EVID_ROOT=/var/lib/wwcx-deployment-evidence/edge1-public-summary-staging-live
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE="$EVID_ROOT/$STAMP"

rollback() {
  set +e
  systemctl disable --now wwcx-edge1-public-summary-stager.timer >/dev/null 2>&1 || true
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

install -d -o root -g root -m 0700 "$EVIDENCE" "$RUNTIME_POLICY_DIR"
install -d -o root -g root -m 0755 "$STAGING_ROOT"
cp "$DESIGN_POLICY" "$EVIDENCE/design-policy.json"
git -C "$REPO" rev-parse HEAD > "$EVIDENCE/revision.txt"
git -C "$REPO" status --short --branch > "$EVIDENCE/repository-status.txt"

[[ -f "$RUNTIME_POLICY" ]] && cp "$RUNTIME_POLICY" "$EVIDENCE/runtime-policy.before" || true
python3 - "$DESIGN_POLICY" "$RUNTIME_POLICY" <<'PY'
import json, os, pathlib, sys, tempfile
source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
value = json.loads(source.read_text(encoding="utf-8"))
assert value["contract"] == "wwcx.edge1-public-summary-staging-policy.v1"
assert value["status"] == "design_only"
assert value["enabled"] is False
assert value["deployment_authorized"] is False
assert value["live_publication_authorized"] is False
assert value["activation_requires_explicit_authorization"] is True
value["status"] = "staging_authorized"
value["enabled"] = True
value["deployment_authorized"] = True
value["live_publication_authorized"] = False
assert value["runtime"]["apache_mutation"] is False
assert value["runtime"]["public_tree_write"] is False
assert value["acceptance"]["no_live_route_change"] is True
fd, temporary = tempfile.mkstemp(prefix=".public-summary-staging.", dir=target.parent)
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

cd "$REPO"
python3 -m unittest -v tests.test_edge1_public_summary_stager > "$EVIDENCE/unit-tests.txt" 2>&1
[[ -f "$SERVICE_DST" ]] && cp "$SERVICE_DST" "$EVIDENCE/service.before" || true
[[ -f "$TIMER_DST" ]] && cp "$TIMER_DST" "$EVIDENCE/timer.before" || true
install -o root -g root -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
install -o root -g root -m 0644 "$TIMER_SRC" "$TIMER_DST"
systemctl daemon-reload
systemd-analyze verify "$SERVICE_DST" "$TIMER_DST" > "$EVIDENCE/systemd-verify.txt" 2>&1
systemctl start wwcx-edge1-public-summary-stager.service

python3 - "$STAGING_ROOT" <<'PY'
import json, pathlib, stat, sys
root = pathlib.Path(sys.argv[1])
current = root / "current"
assert current.is_symlink()
release = current.resolve(strict=True)
assert release.parent == (root / "releases").resolve()
expected = {
    "index.html",
    "app.js",
    "style.css",
    "public/status.json",
}
actual = {
    str(path.relative_to(release))
    for path in release.rglob("*")
    if path.is_file()
}
assert actual == expected, (actual, expected)
for relative in expected:
    path = release / relative
    assert path.is_file() and not path.is_symlink()
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
status = json.loads((release / "public/status.json").read_text(encoding="utf-8"))
assert status["contract"] == "wwcx.edge1-public-status.v1"
assert "source_paths" not in status
assert "internal" not in status
print(json.dumps({
    "release": str(release),
    "assets": sorted(actual),
    "overall_state": status.get("overall_state"),
}, indent=2, sort_keys=True))
PY

systemctl enable --now wwcx-edge1-public-summary-stager.timer
systemctl is-enabled wwcx-edge1-public-summary-stager.timer > "$EVIDENCE/timer-enabled.txt"
systemctl is-active wwcx-edge1-public-summary-stager.timer > "$EVIDENCE/timer-active.txt"
systemctl status wwcx-edge1-public-summary-stager.service wwcx-edge1-public-summary-stager.timer --no-pager > "$EVIDENCE/systemd-status.txt" 2>&1 || true
journalctl -u wwcx-edge1-public-summary-stager.service -n 50 --no-pager > "$EVIDENCE/journal.txt" 2>&1
readlink -f "$STAGING_ROOT/current" > "$EVIDENCE/current-release.txt"
CURRENT=$(cat "$EVIDENCE/current-release.txt")
find "$CURRENT" -type f -print0 | sort -z | xargs -0 sha256sum > "$EVIDENCE/release-sha256.txt"
cp "$CURRENT/public/status.json" "$EVIDENCE/public-status.json"
ss -lntup > "$EVIDENCE/listeners-after.txt"

python3 - "$EVIDENCE" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
status = json.loads((root / "public-status.json").read_text(encoding="utf-8"))
result = {
    "contract": "wwcx.edge1-public-summary-staging-live-acceptance.v1",
    "state": "staged",
    "overall_state": status.get("overall_state"),
    "timer_enabled": (root / "timer-enabled.txt").read_text().strip() == "enabled",
    "timer_active": (root / "timer-active.txt").read_text().strip() == "active",
    "committed_policy_remained_fail_closed": True,
    "runtime_policy_root_only": True,
    "live_publication_authorized": False,
    "apache_changed": False,
    "public_tree_changed": False,
    "public_route_changed": False,
    "network_listener_added": False,
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
