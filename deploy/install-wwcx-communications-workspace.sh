#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE=${1:-}
UNIT_NAME=wwcx-communications-workspace.service
UNIT=/etc/systemd/system/$UNIT_NAME
SOURCE_UNIT=$ROOT/deploy/wwcx-communications-workspace.service
RUNNER=$ROOT/deploy/run-wwcx-communications-workspace.sh
HOST=127.0.0.1
PORT=8095
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/var/backups/wwcx-communications-workspace-$STAMP

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

python3 - "$ROOT/server/unified_communications_server.py" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("workspace_server_syntax=PASS")
PY

sh -n "$RUNNER"
[ -f "$SOURCE_UNIT" ] || { echo "missing service unit: $SOURCE_UNIT" >&2; exit 1; }
[ -f "$RUNNER" ] || { echo "missing runner: $RUNNER" >&2; exit 1; }

case "$MODE" in
  "")
    echo "Dry run passed. Use --apply to install the loopback-only read-only service."
    exit 0
    ;;
  --apply) ;;
  *)
    echo "unknown argument: $MODE" >&2
    exit 1
    ;;
esac

id wwadmin >/dev/null 2>&1 || { echo "required service account wwadmin is missing" >&2; exit 1; }

EXISTING_LISTENER=$(ss -lnt 2>/dev/null | awk -v p=":$PORT" '$4 ~ p"$" {print $4; exit}')
if [ -n "$EXISTING_LISTENER" ] && ! systemctl is-active --quiet "$UNIT_NAME"; then
  echo "port $PORT is already in use by another listener: $EXISTING_LISTENER" >&2
  exit 1
fi

mkdir -p "$BACKUP"
HAD_UNIT=0
WAS_ACTIVE=0
WAS_ENABLED=0

if [ -f "$UNIT" ]; then
  HAD_UNIT=1
  cp -a "$UNIT" "$BACKUP/$UNIT_NAME"
fi
if systemctl is-active --quiet "$UNIT_NAME"; then
  WAS_ACTIVE=1
fi
if systemctl is-enabled --quiet "$UNIT_NAME" 2>/dev/null; then
  WAS_ENABLED=1
fi

rollback() {
  rc=$?
  trap - EXIT HUP INT TERM
  echo "workspace activation failed; restoring previous service state" >&2
  if [ "$HAD_UNIT" -eq 1 ]; then
    install -o root -g root -m 0644 "$BACKUP/$UNIT_NAME" "$UNIT"
  else
    rm -f "$UNIT"
  fi
  systemctl daemon-reload || true
  if [ "$WAS_ENABLED" -eq 1 ]; then
    systemctl enable "$UNIT_NAME" >/dev/null 2>&1 || true
  else
    systemctl disable "$UNIT_NAME" >/dev/null 2>&1 || true
  fi
  if [ "$WAS_ACTIVE" -eq 1 ]; then
    systemctl restart "$UNIT_NAME" || true
  else
    systemctl stop "$UNIT_NAME" >/dev/null 2>&1 || true
  fi
  echo "rollback_backup=$BACKUP" >&2
  exit "$rc"
}
trap rollback EXIT HUP INT TERM

chmod 0755 "$RUNNER"
install -o root -g root -m 0644 "$SOURCE_UNIT" "$UNIT"
systemctl daemon-reload
systemctl enable --now "$UNIT_NAME"

healthy=0
for i in $(seq 1 20); do
  if curl -fsS "http://$HOST:$PORT/communications/healthz" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done
if [ "$healthy" -ne 1 ]; then
  journalctl -u "$UNIT_NAME" -n 100 --no-pager >&2 || true
  exit 1
fi

curl -fsS "http://$HOST:$PORT/communications/healthz" | python3 -m json.tool >/dev/null
curl -fsS "http://$HOST:$PORT/communications/api/v1/readiness" | python3 -m json.tool >/dev/null
curl -fsS "http://$HOST:$PORT/communications/api/v1/events?limit=1" | python3 -m json.tool >/dev/null

POST_CODE=$(curl -sS -o "$BACKUP/post-response.json" -w '%{http_code}' -X POST "http://$HOST:$PORT/communications/api/v1/events")
[ "$POST_CODE" = "405" ] || { echo "mutation boundary failed: POST returned $POST_CODE" >&2; exit 1; }
python3 - "$BACKUP/post-response.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as fh:
    value = json.load(fh)
assert value.get("mutation_authorized") is False
assert value.get("error") == "read_only_workspace"
print("mutation_boundary=PASS")
PY

ss -lnt | grep -F "$HOST:$PORT" >/dev/null
if ss -lnt | grep -E "0\\.0\\.0\\.0:$PORT|\\[::\\]:$PORT" >/dev/null; then
  echo "workspace unexpectedly exposed on a wildcard listener" >&2
  exit 1
fi

trap - EXIT HUP INT TERM

echo "WW.CX Communications workspace installed read-only on http://$HOST:$PORT/communications/."
echo "rollback_backup=$BACKUP"
if [ -f /etc/wwcx-communications-workspace.env ]; then
  echo "optional_environment_file=/etc/wwcx-communications-workspace.env"
else
  echo "canonical_snapshot=not_attached"
fi
