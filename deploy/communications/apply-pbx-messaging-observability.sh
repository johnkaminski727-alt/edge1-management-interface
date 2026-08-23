#!/bin/bash
set -euo pipefail
umask 077

AUTHORIZATION=WWCX-PBX-MESSAGING-OBSERVABILITY-001
REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
EVIDENCE_ROOT=${EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/pbx-messaging-observability}
TELEPHONY_SERVICE=wwcx-telephony-console.service
ASTERISK_SERVICE=asterisk.service
MESSAGING_SERVICE=wwcx-messaging-gateway.service
TELEPHONY_SOURCE=server/telephony_status_server.py
CAPTURE_TOOL=tools/communications/capture-pbx-messaging-runtime.sh

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if [ "$#" -ne 5 ] \
  || [ "$1" != "--authorization" ] \
  || [ "$2" != "$AUTHORIZATION" ] \
  || [ "$3" != "--expected-commit" ] \
  || [ "$5" != "--execute" ]; then
  printf 'Usage: sudo bash %s --authorization %s --expected-commit <40-hex-sha> --execute\n' "$0" "$AUTHORIZATION" >&2
  exit 2
fi
EXPECTED_COMMIT=$4
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "expected commit must be a full 40-hex SHA"
[ "${EUID:-$(id -u)}" -eq 0 ] || fail "run as root"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found at $REPO_ROOT"

HOST=$(hostname -f 2>/dev/null || hostname)
[ "$HOST" = "edge1.ww.cx" ] || fail "expected edge1.ww.cx, got $HOST"

BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
[ "$BRANCH" = "main" ] || fail "repository must be on main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository working tree is not clean"
HEAD=$(git -C "$REPO_ROOT" rev-parse HEAD)
[ "$HEAD" = "$EXPECTED_COMMIT" ] || fail "HEAD $HEAD does not match approved commit $EXPECTED_COMMIT"

for path in \
  "$REPO_ROOT/$TELEPHONY_SOURCE" \
  "$REPO_ROOT/$CAPTURE_TOOL" \
  "$REPO_ROOT/tests/validate_telephony_console.py" \
  "$REPO_ROOT/tests/validate_telephony_pbx_observability.py" \
  "$REPO_ROOT/tests/validate_telephony_planned_peers.py" \
  "$REPO_ROOT/tests/validate_messaging_mms_runtime_observability.py"
do
  [ -f "$path" ] || fail "required reviewed asset missing: $path"
done

for service in "$TELEPHONY_SERVICE" "$ASTERISK_SERVICE" "$MESSAGING_SERVICE"; do
  systemctl is-active --quiet "$service" || fail "$service is not active before reconciliation"
done

TELEPHONY_FRAGMENT=$(systemctl show "$TELEPHONY_SERVICE" -p FragmentPath --value)
[ -n "$TELEPHONY_FRAGMENT" ] && [ -f "$TELEPHONY_FRAGMENT" ] \
  || fail "telephony console unit fragment is unavailable"
grep -Fq '/opt/edge1-management-interface/server/telephony_status_server.py' "$TELEPHONY_FRAGMENT" \
  || fail "installed telephony console is not using the reviewed repository source"
grep -Fq -- '--host 127.0.0.1 --port 8096' "$TELEPHONY_FRAGMENT" \
  || fail "installed telephony console listener contract is unexpected"

mkdir -p "$EVIDENCE_ROOT"
chmod 0700 "$EVIDENCE_ROOT"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
mkdir -m 0700 "$EVIDENCE_DIR"

ASTERISK_PID_BEFORE=$(systemctl show "$ASTERISK_SERVICE" -p MainPID --value)
MESSAGING_PID_BEFORE=$(systemctl show "$MESSAGING_SERVICE" -p MainPID --value)
TELEPHONY_PID_BEFORE=$(systemctl show "$TELEPHONY_SERVICE" -p MainPID --value)
printf 'commit=%s\nasterisk_pid=%s\nmessaging_pid=%s\ntelephony_pid=%s\n' \
  "$HEAD" "$ASTERISK_PID_BEFORE" "$MESSAGING_PID_BEFORE" "$TELEPHONY_PID_BEFORE" \
  > "$EVIDENCE_DIR/before.txt"

ss -lntup | awk '$5 ~ /:8096$/ {print $1, $5}' > "$EVIDENCE_DIR/telephony-listener-before.txt"
if grep -Ev '127\.0\.0\.1:8096|\[::1\]:8096|::1:8096' "$EVIDENCE_DIR/telephony-listener-before.txt" | grep . >/dev/null 2>&1; then
  fail "telephony console port 8096 is exposed outside loopback"
fi

cd "$REPO_ROOT"
python3 tests/validate_telephony_console.py > "$EVIDENCE_DIR/validate-telephony-console.txt"
python3 tests/validate_telephony_pbx_observability.py > "$EVIDENCE_DIR/validate-pbx-observability.txt"
python3 tests/validate_telephony_planned_peers.py > "$EVIDENCE_DIR/validate-planned-peers.txt"
python3 tests/validate_messaging_mms_runtime_observability.py > "$EVIDENCE_DIR/validate-mms-observability.txt"

PARENT=$(git rev-parse HEAD^)
git show "$PARENT:$TELEPHONY_SOURCE" > "$EVIDENCE_DIR/telephony-source-parent.py"
cp -a "$TELEPHONY_SOURCE" "$EVIDENCE_DIR/telephony-source-reviewed.py"

rollback_armed=1
rollback_console() {
  status=$?
  trap - ERR INT TERM
  if [ "${rollback_armed:-0}" -eq 1 ]; then
    printf 'Telephony console reconciliation failed; restoring parent runtime source for service recovery.\n' >&2
    cp "$EVIDENCE_DIR/telephony-source-parent.py" "$REPO_ROOT/$TELEPHONY_SOURCE"
    chown --reference="$EVIDENCE_DIR/telephony-source-reviewed.py" "$REPO_ROOT/$TELEPHONY_SOURCE" 2>/dev/null || true
    chmod --reference="$EVIDENCE_DIR/telephony-source-reviewed.py" "$REPO_ROOT/$TELEPHONY_SOURCE" 2>/dev/null || true
    systemctl restart "$TELEPHONY_SERVICE" >/dev/null 2>&1 || true
    cp "$EVIDENCE_DIR/telephony-source-reviewed.py" "$REPO_ROOT/$TELEPHONY_SOURCE"
    chown --reference="$EVIDENCE_DIR/telephony-source-reviewed.py" "$REPO_ROOT/$TELEPHONY_SOURCE" 2>/dev/null || true
    chmod --reference="$EVIDENCE_DIR/telephony-source-reviewed.py" "$REPO_ROOT/$TELEPHONY_SOURCE" 2>/dev/null || true
    printf 'rollback_performed=true\n' > "$EVIDENCE_DIR/rollback.txt"
  fi
  exit "$status"
}
trap rollback_console ERR INT TERM

systemctl restart "$TELEPHONY_SERVICE"
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS --max-time 2 http://127.0.0.1:8096/healthz > "$EVIDENCE_DIR/telephony-health.json"; then
    break
  fi
  sleep 1
done
[ -s "$EVIDENCE_DIR/telephony-health.json" ] || fail "telephony console health did not recover"

curl -fsS --max-time 3 http://127.0.0.1:8096/api/telephony/status \
  > "$EVIDENCE_DIR/telephony-status.json"
python3 - "$EVIDENCE_DIR/telephony-status.json" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["mode"] == "live_read_only"
metrics = payload["metrics"]
assert metrics["trunks_total"] == 1, metrics
assert metrics["trunks_healthy"] == 1, metrics
assert metrics["trunks_planned"] == 1, metrics
planned = [item for item in payload["interconnects"] if item.get("name") == "lab-carrier-001-peer"]
assert len(planned) == 1, planned
assert planned[0]["status"] == "planned", planned[0]
assert planned[0]["health_check_applicable"] is False, planned[0]
PY

for service in "$ASTERISK_SERVICE" "$MESSAGING_SERVICE" "$TELEPHONY_SERVICE"; do
  systemctl is-active --quiet "$service" || fail "$service is not active after reconciliation"
done
ASTERISK_PID_AFTER=$(systemctl show "$ASTERISK_SERVICE" -p MainPID --value)
MESSAGING_PID_AFTER=$(systemctl show "$MESSAGING_SERVICE" -p MainPID --value)
TELEPHONY_PID_AFTER=$(systemctl show "$TELEPHONY_SERVICE" -p MainPID --value)
[ "$ASTERISK_PID_AFTER" = "$ASTERISK_PID_BEFORE" ] || fail "Asterisk PID changed unexpectedly"
[ "$MESSAGING_PID_AFTER" = "$MESSAGING_PID_BEFORE" ] || fail "Messaging Gateway PID changed unexpectedly"

ss -lntup | awk '$5 ~ /:8096$/ {print $1, $5}' > "$EVIDENCE_DIR/telephony-listener-after.txt"
if grep -Ev '127\.0\.0\.1:8096|\[::1\]:8096|::1:8096' "$EVIDENCE_DIR/telephony-listener-after.txt" | grep . >/dev/null 2>&1; then
  fail "telephony console port 8096 is exposed outside loopback after restart"
fi

PYTHONPATH="$REPO_ROOT/server" python3 "$REPO_ROOT/server/messaging_gateway_collector.py" \
  > "$EVIDENCE_DIR/messaging-observability.json"
RUNTIME_EVIDENCE=$(EVIDENCE_ROOT="$EVIDENCE_DIR" EXPECTED_HOST=edge1.ww.cx \
  bash "$REPO_ROOT/$CAPTURE_TOOL")
printf '%s\n' "$RUNTIME_EVIDENCE" > "$EVIDENCE_DIR/runtime-capture-path.txt"

printf 'asterisk_pid=%s\nmessaging_pid=%s\ntelephony_pid=%s\n' \
  "$ASTERISK_PID_AFTER" "$MESSAGING_PID_AFTER" "$TELEPHONY_PID_AFTER" \
  > "$EVIDENCE_DIR/after.txt"
printf 'rollback_performed=false\n' > "$EVIDENCE_DIR/rollback.txt"

(
  cd "$EVIDENCE_DIR"
  find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort \
    | while IFS= read -r file; do sha256sum "$file"; done > SHA256SUMS
)
chmod -R go-rwx "$EVIDENCE_DIR"

rollback_armed=0
trap - ERR INT TERM

printf 'PBX + Messaging observability reconciliation accepted.\n'
printf 'Telephony console restarted: yes\n'
printf 'Asterisk restarted: no\n'
printf 'Messaging Gateway restarted: no\n'
printf 'Call/SMS/MMS traffic generated: no\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
