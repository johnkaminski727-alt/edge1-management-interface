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

install -m 0644 "$UNIT_SOURCE" "$UNIT_TARGET"
systemctl daemon-reload
systemctl enable --now wwcx-telephony-console.service

sleep 1
curl -fsS http://127.0.0.1:8096/healthz >/dev/null
curl -fsS http://127.0.0.1:8096/api/telephony/status >/dev/null

if ss -lnt | grep -E '0\.0\.0\.0:8096|\[::\]:8096' >/dev/null; then
  echo "ERROR: unsafe public listener detected on 8096" >&2
  exit 1
fi

echo "Telephony console installed successfully."
echo "Local URL: http://127.0.0.1:8096/"
