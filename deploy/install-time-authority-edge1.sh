#!/bin/sh
set -eu

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
SERVICE_USER=${EDGE1_TIME_AUTHORITY_USER:-bigbird-time}
DATA_DIR=${EDGE1_TIME_AUTHORITY_DATA_DIR:-/var/lib/edge1-time-authority}

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root." >&2
  exit 1
fi

test -r "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py"
test -r "$REPO_ROOT/modules/time-authority/config/sources.json"
python3 -m json.tool "$REPO_ROOT/modules/time-authority/config/sources.json" >/dev/null
python3 "$REPO_ROOT/tests/validate_time_authority.py"

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR"
chmod 0755 "$REPO_ROOT/tools/time_authority/collect-edge1.sh" "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py"
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.service" /etc/systemd/system/
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.timer" /etc/systemd/system/
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-dashboard.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now edge1-time-authority-collector.timer
systemctl enable --now edge1-time-authority-dashboard.service
systemctl start edge1-time-authority-collector.service

curl -fsS http://127.0.0.1:8092/healthz >/dev/null
echo "WW.CX Time Authority installed on Edge1."
