#!/bin/sh
set -eu

SERVICE_NAME=edge1-operator.service
SERVICE_DIR=/etc/systemd/system
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

printf 'Installing %s\n' "$SERVICE_NAME"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root." >&2
    exit 1
fi

install -m 0644 "$SOURCE_DIR/edge1-operator.service" "$SERVICE_DIR/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

printf '