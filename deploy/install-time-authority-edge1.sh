#!/bin/sh
set -eu

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
SERVICE_USER=${EDGE1_TIME_AUTHORITY_USER:-bigbird-time}
DATA_DIR=${EDGE1_TIME_AUTHORITY_DATA_DIR:-/var/lib/edge1-time-authority}
UNIT_DIR=${EDGE1_TIME_AUTHORITY_UNIT_DIR:-/etc/systemd/system}
SYSTEMCTL_BIN=${EDGE1_TIME_AUTHORITY_SYSTEMCTL:-systemctl}
SIMULATION=${EDGE1_TIME_AUTHORITY_SIMULATION:-0}
BACKUP_ROOT=${EDGE1_TIME_AUTHORITY_BACKUP_ROOT:-/var/lib/wwcx-deployment-evidence/time-authority}

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

EDGE1_MANAGEMENT_ROOT=$REPO_ROOT \
EDGE1_TIME_AUTHORITY_SIMULATION=$SIMULATION \
EDGE1_TIME_AUTHORITY_UNIT_DIR=$UNIT_DIR \
EDGE1_TIME_AUTHORITY_SYSTEMCTL=$SYSTEMCTL_BIN \
  "$REPO_ROOT/deploy/time-authority-edge1-preflight.sh"

if [ "$SIMULATION" != "1" ] && ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

if [ "$SIMULATION" = "1" ]; then
  install -d -m 0750 "$DATA_DIR" "$UNIT_DIR"
else
  # The service account owns only its application data. The global systemd
  # unit directory is a root-controlled trust boundary and must never be
  # chowned to a service principal.
  install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR"

  UNIT_DIR_OWNER=$(stat -c '%U:%G' "$UNIT_DIR" 2>/dev/null || true)
  UNIT_DIR_MODE=$(stat -c '%a' "$UNIT_DIR" 2>/dev/null || true)
  if [ "$UNIT_DIR_OWNER" != "root:root" ] || [ "$UNIT_DIR_MODE" != "755" ]; then
    echo "Refusing Time Authority install: systemd unit directory must remain root:root mode 755; found $UNIT_DIR_OWNER mode $UNIT_DIR_MODE at $UNIT_DIR" >&2
    exit 1
  fi

  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  BACKUP_DIR="$BACKUP_ROOT/install-$STAMP"
  install -d -m 0750 "$BACKUP_ROOT" "$BACKUP_DIR"
  for unit_name in \
    edge1-time-authority-collector.service \
    edge1-time-authority-collector.timer \
    edge1-time-authority-dashboard.service; do
    if [ -f "$UNIT_DIR/$unit_name" ]; then
      install -m 0644 "$UNIT_DIR/$unit_name" "$BACKUP_DIR/$unit_name"
    fi
  done
  {
    echo "installed_at_utc=$STAMP"
    echo "repository=$REPO_ROOT"
    echo "repository_head=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "systemd_unit_dir=$UNIT_DIR"
    echo "systemd_unit_dir_owner=$UNIT_DIR_OWNER"
    echo "systemd_unit_dir_mode=$UNIT_DIR_MODE"
  } >"$BACKUP_DIR/install-metadata.txt"
  chmod 0640 "$BACKUP_DIR/install-metadata.txt"
fi

chmod 0755 "$REPO_ROOT/tools/time_authority/collect-edge1.sh" "$REPO_ROOT/tools/time_authority/ntp_rtt_probe.py"
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.service" "$UNIT_DIR/"
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-collector.timer" "$UNIT_DIR/"
install -m 0644 "$REPO_ROOT/deploy/systemd/edge1-time-authority-dashboard.service" "$UNIT_DIR/"

"$SYSTEMCTL_BIN" daemon-reload
"$SYSTEMCTL_BIN" enable --now edge1-time-authority-collector.timer
"$SYSTEMCTL_BIN" enable edge1-time-authority-dashboard.service
"$SYSTEMCTL_BIN" restart edge1-time-authority-dashboard.service
"$SYSTEMCTL_BIN" start edge1-time-authority-collector.service

"$REPO_ROOT/deploy/time-authority-edge1-smoke-test.sh"
if [ "$SIMULATION" != "1" ]; then
  echo "Rollback evidence: $BACKUP_DIR"
fi
echo "WW.CX Time Authority installed on Edge1."
