#!/bin/bash
set -euo pipefail
umask 077

REPO=/opt/edge1-management-interface
SOURCE_REL=server/edge1_operator_privileged_broker.py
HELPER_REL=server/asterisk_process_identity.py
UNIT_REL=deploy/edge1-operator/edge1-operator-privileged-broker.service
SERVICE=edge1-operator-privileged-broker.service
ROOT=/usr/local/libexec/edge1-operator-privileged-broker
RELEASES=$ROOT/releases
CURRENT=$ROOT/current
UNIT=/etc/systemd/system/$SERVICE
SOCKET=/run/edge1-operator-privileged/control.sock
EVID_ROOT=/var/lib/wwcx-deployment-evidence/operator-privileged-broker
MODE=dry-run
EXPECTED_COMMIT=

usage() {
  echo "usage: sudo bash $0 --expected-commit <40-hex-sha> [--apply]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --expected-commit)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      EXPECTED_COMMIT=$2
      shift 2
      ;;
    --apply)
      MODE=apply
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "full expected commit is required" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root/sudo" >&2; exit 3; }
[ "$(hostname -f)" = edge1.ww.cx ] || { echo "expected edge1.ww.cx" >&2; exit 4; }
[ -d "$REPO/.git" ] || { echo "repository missing" >&2; exit 5; }

HEAD=$(git -C "$REPO" rev-parse HEAD)
[ "$HEAD" = "$EXPECTED_COMMIT" ] || { echo "HEAD $HEAD does not match approved $EXPECTED_COMMIT" >&2; exit 6; }
[ -z "$(git -C "$REPO" status --porcelain)" ] || { echo "repository working tree is not clean" >&2; exit 7; }
[ -f "$REPO/$SOURCE_REL" ] || { echo "broker source missing" >&2; exit 8; }
[ -f "$REPO/$HELPER_REL" ] || { echo "Asterisk identity helper missing" >&2; exit 8; }
[ -f "$REPO/$UNIT_REL" ] || { echo "broker unit missing" >&2; exit 9; }
getent passwd wwadmin >/dev/null || { echo "wwadmin account missing" >&2; exit 10; }
getent group wwadmin >/dev/null || { echo "wwadmin group missing" >&2; exit 11; }

python3 -m py_compile "$REPO/$SOURCE_REL" "$REPO/$HELPER_REL"
if grep -Eq 'edge1_agent_exec|/bin/sh|-lc|shell=True|subprocess\.(Popen|call|check_call|check_output).*[^[]' "$REPO/$SOURCE_REL"; then
  echo "broker source contains a forbidden generic shell pattern" >&2
  exit 12
fi
grep -Fq 'TELEPHONY_SERVICE = "wwcx-telephony-console.service"' "$REPO/$SOURCE_REL" || { echo "fixed service constant missing" >&2; exit 13; }
grep -Fq 'RestrictAddressFamilies=AF_UNIX' "$REPO/$UNIT_REL" || { echo "AF_UNIX-only unit restriction missing" >&2; exit 14; }
grep -Fq 'NoNewPrivileges=true' "$REPO/$UNIT_REL" || { echo "NoNewPrivileges restriction missing" >&2; exit 15; }
grep -Fxq 'CapabilityBoundingSet=' "$REPO/$UNIT_REL" || { echo "empty capability bounding set missing" >&2; exit 16; }
grep -Fxq 'AmbientCapabilities=' "$REPO/$UNIT_REL" || { echo "empty ambient capability set missing" >&2; exit 17; }

SOURCE_SHA=$(sha256sum "$REPO/$SOURCE_REL" | awk '{print $1}')
HELPER_SHA=$(sha256sum "$REPO/$HELPER_REL" | awk '{print $1}')
UNIT_SHA=$(sha256sum "$REPO/$UNIT_REL" | awk '{print $1}')
RELEASE=$RELEASES/$EXPECTED_COMMIT

if [ "$MODE" = dry-run ]; then
  echo "Privileged broker install dry run passed."
  echo "commit=$EXPECTED_COMMIT"
  echo "source_sha256=$SOURCE_SHA"
  echo "helper_sha256=$HELPER_SHA"
  echo "unit_sha256=$UNIT_SHA"
  echo "release=$RELEASE"
  echo "No files or services were changed."
  exit 0
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVID=$EVID_ROOT/$STAMP
install -d -o root -g root -m 0700 "$EVID"

if [ -L "$CURRENT" ]; then
  readlink "$CURRENT" > "$EVID/current.before.txt"
else
  : > "$EVID/current.before.txt"
fi
if [ -e "$UNIT" ]; then
  cp -a "$UNIT" "$EVID/service.before"
  echo yes > "$EVID/unit_existed.before"
else
  echo no > "$EVID/unit_existed.before"
fi
systemctl is-enabled "$SERVICE" > "$EVID/enabled.before.txt" 2>&1 || true
systemctl is-active "$SERVICE" > "$EVID/active.before.txt" 2>&1 || true

install -d -o root -g root -m 0555 "$ROOT" "$RELEASES"
if [ -e "$RELEASE" ]; then
  [ -f "$RELEASE/edge1_operator_privileged_broker.py" ] || { echo "existing release is invalid" >&2; exit 20; }
  [ -f "$RELEASE/asterisk_process_identity.py" ] || { echo "existing release helper is invalid" >&2; exit 20; }
  EXISTING=$(sha256sum "$RELEASE/edge1_operator_privileged_broker.py" | awk '{print $1}')
  EXISTING_HELPER=$(sha256sum "$RELEASE/asterisk_process_identity.py" | awk '{print $1}')
  [ "$EXISTING" = "$SOURCE_SHA" ] || { echo "existing immutable release hash mismatch" >&2; exit 21; }
  [ "$EXISTING_HELPER" = "$HELPER_SHA" ] || { echo "existing immutable helper hash mismatch" >&2; exit 21; }
else
  install -d -o root -g root -m 0555 "$RELEASE"
  install -o root -g root -m 0444 "$REPO/$SOURCE_REL" "$RELEASE/edge1_operator_privileged_broker.py"
  install -o root -g root -m 0444 "$REPO/$HELPER_REL" "$RELEASE/asterisk_process_identity.py"
fi

TMP_LINK=$ROOT/.current-$STAMP
ln -s "releases/$EXPECTED_COMMIT" "$TMP_LINK"
mv -Tf "$TMP_LINK" "$CURRENT"
chown -h root:root "$CURRENT"
install -o root -g root -m 0644 "$REPO/$UNIT_REL" "$UNIT"

cat > "$EVID/rollback.sh" <<EOF
#!/bin/bash
set -euo pipefail
if [ -s '$EVID/current.before.txt' ]; then
  target=\$(cat '$EVID/current.before.txt')
  tmp='$ROOT/.rollback-current'
  rm -f "\$tmp"
  ln -s "\$target" "\$tmp"
  mv -Tf "\$tmp" '$CURRENT'
else
  rm -f '$CURRENT'
fi
if [ "\$(cat '$EVID/unit_existed.before')" = yes ]; then
  cp -a '$EVID/service.before' '$UNIT'
else
  rm -f '$UNIT'
fi
systemctl daemon-reload
if [ "\$(cat '$EVID/enabled.before.txt')" = enabled ]; then systemctl enable '$SERVICE' >/dev/null; else systemctl disable '$SERVICE' >/dev/null 2>&1 || true; fi
if [ "\$(cat '$EVID/active.before.txt')" = active ]; then systemctl restart '$SERVICE'; else systemctl stop '$SERVICE' >/dev/null 2>&1 || true; fi
echo 'Privileged broker rollback complete.'
EOF
chmod 0700 "$EVID/rollback.sh"

rollback_armed=1
rollback_on_exit() {
  status=$?
  if [ "${rollback_armed:-0}" -eq 1 ]; then
    rollback_armed=0
    echo "Privileged broker install failed; capturing bounded evidence and rolling back." >&2
    systemctl show "$SERVICE" -p Id -p LoadState -p ActiveState -p SubState -p MainPID -p ExecMainStatus > "$EVID/service.failure.txt" 2>&1 || true
    journalctl -u "$SERVICE" -n 80 --no-pager > "$EVID/journal.failure.txt" 2>&1 || true
    if [ -e "$SOCKET" ]; then
      stat -c 'mode=%a owner=%U:%G type=%F' "$SOCKET" > "$EVID/socket.failure.txt" 2>&1 || true
    fi
    echo "evidence=$EVID" >&2
    echo "rollback=$EVID/rollback.sh" >&2
    "$EVID/rollback.sh" || true
  fi
  exit "$status"
}
trap rollback_on_exit EXIT

probe_peer_denial() {
  python3 - "$SOCKET" <<'PY'
import json
import socket
import sys

path = sys.argv[1]
request = {
    "version": 1,
    "action": "telephony_console_reload",
    "request_id": "installer-peer-denial-0001",
    "expected_pid": 1,
    "expected_source_sha256": "0" * 64,
    "expected_repo_head": "0" * 40,
}
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1.0)
        client.connect(path)
        client.sendall((json.dumps(request, sort_keys=True) + "\n").encode())
        client.shutdown(socket.SHUT_WR)
        raw = client.recv(4096).decode().strip()
except (OSError, TimeoutError):
    raise SystemExit(1)
try:
    value = json.loads(raw)
except (TypeError, json.JSONDecodeError):
    raise SystemExit(1)
expected = {"version": 1, "status": "error", "error": "request_denied"}
raise SystemExit(0 if value == expected else 1)
PY
}

systemctl daemon-reload
systemd-analyze verify "$SERVICE"
systemctl enable "$SERVICE" >/dev/null
# Always restart, even when the broker was already active. This guarantees the
# process now serving the socket loaded the newly selected immutable release.
systemctl restart "$SERVICE"

READY=0
READINESS_ATTEMPT=0
for attempt in $(seq 1 40); do
  READINESS_ATTEMPT=$attempt
  if systemctl is-active --quiet "$SERVICE" && [ -S "$SOCKET" ] && probe_peer_denial; then
    READY=1
    break
  fi
  sleep 0.25
done
if [ "$READY" -ne 1 ]; then
  echo "broker did not become connectable with the expected peer-denial response" >&2
  exit 23
fi

MODE=$(stat -c '%a' "$SOCKET")
OWNER=$(stat -c '%U:%G' "$SOCKET")
if [ "$MODE" != 660 ]; then
  echo "unexpected socket mode $MODE" >&2
  exit 25
fi
if [ "$OWNER" != root:wwadmin ]; then
  echo "unexpected socket owner $OWNER" >&2
  exit 26
fi
CURRENT_RELEASE=$(readlink -f "$CURRENT")
if [ "$CURRENT_RELEASE" != "$RELEASE" ]; then
  echo "current broker release does not resolve to reviewed release" >&2
  exit 27
fi
BROKER_PID=$(systemctl show "$SERVICE" -p MainPID --value)
if ! [[ "$BROKER_PID" =~ ^[1-9][0-9]*$ ]]; then
  echo "broker MainPID is unavailable" >&2
  exit 28
fi

systemctl cat "$SERVICE" > "$EVID/service.after.txt"
{
  echo "commit=$EXPECTED_COMMIT"
  echo "release=$RELEASE"
  echo "current_release=$CURRENT_RELEASE"
  echo "broker_pid=$BROKER_PID"
  echo "readiness_attempt=$READINESS_ATTEMPT"
  echo "source_sha256=$SOURCE_SHA"
  echo "helper_sha256=$HELPER_SHA"
  echo "unit_sha256=$UNIT_SHA"
  echo "socket_mode=$MODE"
  echo "socket_owner=$OWNER"
  echo "non_operations_peer_denied=true"
  echo "operator_scope_enabled=false"
  echo "operations_safe_gate_enabled=false"
} > "$EVID/acceptance.txt"
sha256sum "$RELEASE/edge1_operator_privileged_broker.py" "$RELEASE/asterisk_process_identity.py" "$UNIT" > "$EVID/SHA256SUMS"
chmod 0600 "$EVID/acceptance.txt" "$EVID/SHA256SUMS"

rollback_armed=0
trap - EXIT

echo "Privileged broker installation accepted."
echo "service=$SERVICE"
echo "release=$RELEASE"
echo "evidence=$EVID"
echo "rollback=$EVID/rollback.sh"
echo "Operator write scope and Operations API safe-control gate remain separate activation steps."
