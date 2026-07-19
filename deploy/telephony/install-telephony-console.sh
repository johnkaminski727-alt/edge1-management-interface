#!/bin/sh
set -eu

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
UNIT_SOURCE="$REPO_ROOT/deploy/telephony/wwcx-telephony-console.service"
UNIT_TARGET=/etc/systemd/system/wwcx-telephony-console.service

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

for path in \
  "$REPO_ROOT/server/telephony_status_server.py" \
  "$REPO_ROOT/src/web/telephony/index.html" \
  "$REPO_ROOT/src/web/telephony/telephony.js" \
  "$UNIT_SOURCE"; do
  if [ ! -f "$path" ]; then
    echo "Missing required asset: $path" >&2
    exit 1
  fi
done

sed "s#WorkingDirectory=/opt/edge1-management-interface#WorkingDirectory=$REPO_ROOT#; s#/opt/edge1-management-interface/server/telephony_status_server.py#$REPO_ROOT/server/telephony_status_server.py#" \
  "$UNIT_SOURCE" > "$UNIT_TARGET"
chmod 0644 "$UNIT_TARGET"
systemctl daemon-reload
systemctl enable --now wwcx-telephony-console.service

ready=false
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8096/healthz >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done

if [ "$ready" != true ]; then
  systemctl status wwcx-telephony-console.service --no-pager -l >&2 || true
  journalctl -u wwcx-telephony-console.service -n 50 --no-pager >&2 || true
  echo "Telephony console failed to become ready on 127.0.0.1:8096" >&2
  exit 1
fi

curl -fsS http://127.0.0.1:8096/api/telephony/status >/dev/null

if ss -lnt | grep -E '0\.0\.0\.0:8096|\[::\]:8096' >/dev/null; then
  echo "ERROR: unsafe public listener detected on 8096" >&2
  exit 1
fi

echo "Telephony console installed successfully."
echo "Local URL: http://127.0.0.1:8096/"
