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

if [ -d /opt/edge1-management-interface/.git ]; then
    branch=$(git -C /opt/edge1-management-interface branch --show-current 2>/dev/null || true)
    if [ -n "$branch" ] && [ "$branch" != "main" ]; then
        echo "Refusing deployment from non-main branch: $branch" >&2
        exit 1