#!/bin/sh
set -eu

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
SERVICE_USER=${EDGE1_TIME_AUTHORITY_USER:-bigbird-time}
DATA_DIR=${EDGE1_TIME_AUTHORITY_DATA_DIR:-/var/lib/edge1-time-authority}

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root." >&2
  exit 1
fi

EDGE1_MANAGEMENT_ROOT=$REPO_ROOT "$REPO_ROOT/deploy/time-authority-edge1-preflight.sh"

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

"$REPO_ROOT/deploy/time-authority-edge1-smoke-test.sh"
echo "WW.CX Time Authority installed on Edge1."
