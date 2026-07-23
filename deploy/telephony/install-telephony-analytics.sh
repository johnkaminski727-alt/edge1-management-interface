#!/bin/sh
set -eu

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
UNIT_SOURCE="$REPO_ROOT/deploy/telephony/wwcx-telephony-analytics.service"
UNIT_TARGET=/etc/systemd/system/wwcx-telephony-analytics.service

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

for path in \
  "$REPO_ROOT/server/telephony_analytics_api.py" \
  "$REPO_ROOT/server/telephony_platform.py" \
  "$REPO_ROOT/tests/validate_telephony_analytics_api.py" \
  "$UNIT_SOURCE"; do
  if [ ! -f "$path" ]; then
    echo "Missing required asset: $path" >&2
    exit 1
  fi
done

python3 "$REPO_ROOT/tests/validate_telephony_platform.py"
python3 "$REPO_ROOT/tests/validate_telephony_analytics_api.py"

sed "s#WorkingDirectory=/opt/edge1-management-interface#WorkingDirectory=$REPO_ROOT#; s#/opt/edge1-management-interface/server/telephony_analytics_api.py#$REPO_ROOT/server/telephony_analytics_api.py#" \
  "$UNIT_SOURCE" > "$UNIT_TARGET"
chmod 0644 "$UNIT_TARGET"
systemctl daemon-reload
systemctl enable --now wwcx-telephony-analytics.service

ready=false
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8099/healthz >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done

if [ "$ready" != true ]; then
  systemctl status wwcx-telephony-analytics.service --no-pager -l >&2 || true
  journalctl -u wwcx-telephony-analytics.service -n 50 --no-pager >&2 || true
  echo "Telephony analytics failed to become ready on 127.0.0.1:8099" >&2
  exit 1
fi

curl -fsS http://127.0.0.1:8099/api/telephony/platform/health >/dev/null
curl -fsS http://127.0.0.1:8099/api/telephony/platform/calls/summary >/dev/null
curl -fsS http://127.0.0.1:8099/api/telephony/platform/interconnects/summary >/dev/null

if ss -lnt | grep -E '0\.0\.0\.0:8099|\[::\]:8099' >/dev/null; then
  echo "ERROR: unsafe public listener detected on 8099" >&2
  exit 1
fi

echo "Telephony analytics installed successfully."
echo "Local health: http://127.0.0.1:8099/healthz"
