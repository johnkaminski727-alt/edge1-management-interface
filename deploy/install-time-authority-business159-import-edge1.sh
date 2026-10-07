#!/bin/sh
set -eu
ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
DATA_DIR=${EDGE1_TIME_AUTHORITY_DATA_DIR:-/var/lib/edge1-time-authority}
UNIT_DIR=${EDGE1_TIME_AUTHORITY_UNIT_DIR:-/etc/systemd/system}
SYSTEMCTL=${EDGE1_TIME_AUTHORITY_SYSTEMCTL:-systemctl}
DASH_USER=${EDGE1_TIME_AUTHORITY_USER:-bigbird-time}

[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }
[ -x "$ROOT/tools/time_authority/import_business159_public_status.py" ] || { echo "Importer missing." >&2; exit 1; }
[ -f "$ROOT/deploy/systemd/edge1-time-authority-business159-import.service" ] || { echo "Import service missing." >&2; exit 1; }
[ -f "$ROOT/deploy/systemd/edge1-time-authority-business159-import.timer" ] || { echo "Import timer missing." >&2; exit 1; }
[ -f "$ROOT/deploy/systemd/edge1-time-authority-dashboard.service.d/30-business159-observer.conf" ] || { echo "Dashboard drop-in missing." >&2; exit 1; }

install -d -m 0750 -o "$DASH_USER" -g "$DASH_USER" "$DATA_DIR"
if [ ! -e "$DATA_DIR/business159-measurements.jsonl" ]; then
  install -m 0640 -o root -g "$DASH_USER" /dev/null "$DATA_DIR/business159-measurements.jsonl"
else
  chown root:"$DASH_USER" "$DATA_DIR/business159-measurements.jsonl"
  chmod 0640 "$DATA_DIR/business159-measurements.jsonl"
fi
install -m 0644 "$ROOT/deploy/systemd/edge1-time-authority-business159-import.service" "$UNIT_DIR/"
install -m 0644 "$ROOT/deploy/systemd/edge1-time-authority-business159-import.timer" "$UNIT_DIR/"
install -d -m 0755 "$UNIT_DIR/edge1-time-authority-dashboard.service.d"
install -m 0644 "$ROOT/deploy/systemd/edge1-time-authority-dashboard.service.d/30-business159-observer.conf" "$UNIT_DIR/edge1-time-authority-dashboard.service.d/"

"$SYSTEMCTL" daemon-reload
"$SYSTEMCTL" start edge1-time-authority-business159-import.service
"$SYSTEMCTL" enable --now edge1-time-authority-business159-import.timer
"$SYSTEMCTL" restart edge1-time-authority-dashboard.service

ready=0
for _n in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8101/healthz >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[ "$ready" -eq 1 ] || { echo "Time Authority dashboard did not become ready." >&2; exit 1; }
curl -fsS 'http://127.0.0.1:8101/api/time-authority/summary?limit=200' | /usr/bin/python3 -c 'import json,sys; d=json.load(sys.stdin); ids={x["observer_id"] for x in d["observers"]}; assert "edge1" in ids and "business159" in ids, ids'
echo "Business159 Time Authority observer import installed."
