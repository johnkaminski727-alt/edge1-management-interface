#!/bin/sh
set -eu

MODE=dry-run
START=0
for arg in "$@"; do
    case "$arg" in
        --apply) MODE=apply ;;
        --start) START=1 ;;
        --dry-run) MODE=dry-run ;;
        *) echo "usage: $0 [--dry-run|--apply] [--start]" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
UNIT_SOURCE="$SCRIPT_DIR/edge1-comms-relay.service"
CONFIG_SOURCE="$REPO_ROOT/config/comms-relay.example.json"
UNIT_TARGET=/etc/systemd/system/edge1-comms-relay.service
CONFIG_TARGET=/etc/wwcx/comms-relay.json
DATA_DIR=/var/lib/wwcx-comms
SERVICE_USER=wwcx-comms

python3 "$REPO_ROOT/server/edge1_comms_cli.py" config validate "$CONFIG_SOURCE" >/dev/null

echo "Edge1 Comms Relay deployment preflight"
echo "  mode: $MODE"
echo "  repository: $REPO_ROOT"
echo "  unit: $UNIT_TARGET"
echo "  config: $CONFIG_TARGET"
echo "  data: $DATA_DIR"
echo "  start requested: $START"

if [ "$MODE" != apply ]; then
    echo "Dry run only. Re-run with --apply to install files. Add --start only when local service activation is intended."
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "--apply requires root" >&2
    exit 3
fi

if ! getent group "$SERVICE_USER" >/dev/null 2>&1; then
    groupadd --system "$SERVICE_USER"
fi
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$SERVICE_USER" --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -m 0750 -o root -g "$SERVICE_USER" /etc/wwcx
install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR" "$DATA_DIR/config-control"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
if [ -f "$UNIT_TARGET" ]; then
    cp -a "$UNIT_TARGET" "$UNIT_TARGET.$STAMP.bak"
fi
install -m 0644 -o root -g root "$UNIT_SOURCE" "$UNIT_TARGET"

if [ ! -f "$CONFIG_TARGET" ]; then
    install -m 0640 -o root -g "$SERVICE_USER" "$CONFIG_SOURCE" "$CONFIG_TARGET"
    echo "Installed safe loopback-only starter configuration."
else
    python3 "$REPO_ROOT/server/edge1_comms_cli.py" config validate "$CONFIG_TARGET" >/dev/null
    echo "Preserved and validated existing configuration."
fi

systemctl daemon-reload
systemctl cat edge1-comms-relay.service >/dev/null

if [ "$START" -eq 1 ]; then
    systemctl enable --now edge1-comms-relay.service
    systemctl is-active --quiet edge1-comms-relay.service
    echo "Service activated. Verify listeners and health before any network exposure changes."
else
    echo "Installed but not started. Activation remains explicit."
fi
