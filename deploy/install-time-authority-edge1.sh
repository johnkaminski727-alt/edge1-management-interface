#!/bin/sh
set -eu

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
SERVICE_USER=${EDGE1_TIME_AUTHORITY_USER:-bigbird-time}
DATA_DIR=${EDGE1_TIME_AUTHORITY_DATA_DIR:-/var/lib/edge1-time-authority}
UNIT_DIR=${EDGE1_TIME_AUTHORITY_UNIT_DIR:-/etc/systemd/system}
SYSTEMCTL_BIN=${EDGE1_TIME_AUTHORITY_SYSTEMCTL:-systemctl}
SIMULATION=${EDGE1_TIME_AUTHORITY_SIMULATION:-0}

if [ "$SIMULATION" = "1" ]; then
  if [ "$UNIT_DIR" = "/etc/systemd/system" ]; then
    echo "Simulation requires a non-production EDGE1_TIME_AUTHORITY_UNIT_DIR." >&2
    exit 1
  fi
  if [ "$SYSTEMCTL_BIN" = "systemctl" ]; then
    echo "Simulation requires an explicit non-production EDGE1_TIME_AUTHORITY_SYSTEMCTL." >&2
    exit 1
  fi
elif [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root." >&2
  exit 1
fi

EDGE1_MANAGEMENT_ROOT=$REPO_ROOT EDGE1_TIME_AUTHORITY_SIMULATION=$SIMULATION "$REPO_ROOT/deploy/time-authority-edge1-preflight.sh"

if [ "$SIMULATION" != "1" ] && ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

if [ "$SIMULATION" = "1" ]; then
  install -d -m 0750 "$DATA_DIR" "$UNIT_DIR"
else
  install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR" "$UNIT_DIR"
fi
chmod 0755 "$REPO_ROOT/tools/time_authority/collect-edge1.sh" "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py"
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.service" "$UNIT_DIR/"
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.timer" "$UNIT_DIR/"
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-dashboard.service" "$UNIT_DIR/"

"$SYSTEMCTL_BIN" daemon-reload
"$SYSTEMCTL_BIN" enable --now edge1-time-authority-collector.timer
"$SYSTEMCTL_BIN" enable --now edge1-time-authority-dashboard.service
"$SYSTEMCTL_BIN" start edge1-time-authority-collector.service

"$REPO_ROOT/deploy/time-authority-edge1-smoke-test.sh"
echo "WW.CX Time Authority installed on Edge1."
