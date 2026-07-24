#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/edge1-management-interface"
SOURCE="$ROOT/src/web/operations-center/index.html"
DEST="/var/www/edge1-status/index.html"

if [ ! -f "$SOURCE" ]; then
    echo "Missing source: $SOURCE"
    exit 1
fi

sudo install -m 0644 "$SOURCE" "$DEST"

echo "Published Operations Center:"
echo "$DEST"
