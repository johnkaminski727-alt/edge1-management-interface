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

if ! id "$SERVICE_USER" >/dev/null 2>&1