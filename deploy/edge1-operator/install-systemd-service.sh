#!/bin/sh
set -eu

SERVICE_NAME=edge1-operator-mcp.service
SERVICE_DIR=/etc/systemd/system
ENV_DIR=/etc/edge1-operator
ENV_FILE=$ENV_DIR/edge1-operator.env
DATA_DIR=/var/lib/edge1-operator
SERVICE_USER=edge1-operator
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

printf 'Installing %s\n' "$SERVICE_NAME"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root." >&2
    exit 1
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    echo "Creating service user: $SERVICE_USER"
    useradd --system --home /opt/edge1-management-interface --shell /usr/sbin/nologin "$SERVICE_USER"
fi

mkdir -p "$ENV_DIR"
mkdir -p "$DATA_DIR/evidence"

if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" <<EOF
EDGE1_OPERATOR_ENV=production
EDGE1_OPERATOR_ROOT=/opt/edge1-management-interface
EDGE1_OPERATOR_EVIDENCE=$DATA_DIR/evidence
EOF
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"

install -m 0644 "$SOURCE_DIR/$SERVICE_NAME" "$SERVICE_DIR/$SERVICE_NAME"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

printf 'Installed %s\n' "$SERVICE_NAME"
