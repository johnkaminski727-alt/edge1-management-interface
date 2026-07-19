#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE=${1:-}
UNIT=/etc/systemd/system/edge1-operations-api.service
SECRET=/etc/edge1-operations-api.secret
STATE=/var/lib/edge1-operations-api

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
python3 -m py_compile "$ROOT/server/edge1_operations_api.py"
python3 -m json.tool "$ROOT/config/edge1-operations-allowlist.json" >/dev/null
case "$MODE" in
  "") echo "Dry run passed. Use --apply to install the loopback-only service."; exit 0 ;;
  --apply) ;;
  *) echo "unknown argument: $MODE" >&2; exit 1 ;;
esac

install -d -o wwadmin -g wwadmin -m 0700 "$STATE"
if [ ! -e "$SECRET" ]; then
  umask 077
  python3 - <<'PY' >"$SECRET"
import secrets
print(secrets.token_hex(32))
PY
  chown root:wwadmin "$SECRET"
  chmod 0640 "$SECRET"
fi
install -o root -g root -m 0644 "$ROOT/deploy/edge1-operations-api.service" "$UNIT"
systemctl daemon-reload
systemctl enable --now edge1-operations-api.service
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8097/healthz >/dev/null 2>&1; then break; fi
  [ "$i" -lt 20 ] || { journalctl -u edge1-operations-api.service -n 100 --no-pager >&2; exit 1; }
  sleep 1
done
ss -lnt | grep -F '127.0.0.1:8097' >/dev/null
! ss -lnt | grep -E '0\.0\.0\.0:8097|\[::\]:8097' >/dev/null
echo "Edge1 operations API installed on loopback with mutations disabled."
