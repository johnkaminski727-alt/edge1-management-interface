#!/bin/sh
set -eu

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
REPO_ROOT=$(CDPATH= cd -- "$REPO_ROOT" && pwd -P)
APP_ROOT="$REPO_ROOT/services/wwcx-messaging-gateway"
VENV="$APP_ROOT/.venv"
UNIT_SOURCE="$REPO_ROOT/deploy/messaging/wwcx-messaging-gateway.service"
UNIT_TARGET=/etc/systemd/system/wwcx-messaging-gateway.service
SERVICE=wwcx-messaging-gateway.service

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

for path in "$APP_ROOT/pyproject.toml" "$APP_ROOT/app/main.py" "$UNIT_SOURCE"; do
  if [ ! -f "$path" ]; then
    echo "Missing required asset: $path" >&2
    exit 1
  fi
done

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --disable-pip-version-check --no-input -e "$APP_ROOT"

sed \
  -e "s#/opt/edge1-management-interface/services/wwcx-messaging-gateway#$APP_ROOT#g" \
  "$UNIT_SOURCE" > "$UNIT_TARGET"
chmod 0644 "$UNIT_TARGET"

systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"

ready=false
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8095/healthz >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done

if [ "$ready" != true ]; then
  systemctl status "$SERVICE" --no-pager -l >&2 || true
  journalctl -u "$SERVICE" -n 50 --no-pager >&2 || true
  echo "Messaging gateway failed to become ready on 127.0.0.1:8095" >&2
  exit 1
fi

curl -fsS http://127.0.0.1:8095/readyz >/dev/null

if ss -lnt | grep -E '0\.0\.0\.0:8095|\[::\]:8095' >/dev/null; then
  echo "ERROR: unsafe public listener detected on 8095" >&2
  exit 1
fi

main_pid=$(systemctl show "$SERVICE" -p MainPID --value)
listener_pid=$(ss -lntp 2>/dev/null | sed -n 's/.*127\.0\.0\.1:8095.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1)
if [ -z "$main_pid" ] || [ "$main_pid" = 0 ] || [ "$listener_pid" != "$main_pid" ]; then
  echo "ERROR: port 8095 is not owned by the systemd service (service PID=$main_pid, listener PID=${listener_pid:-none})" >&2
  exit 1
fi

echo "Messaging gateway installed successfully."
echo "Health URL: http://127.0.0.1:8095/healthz"
echo "Management controls remain disabled."
