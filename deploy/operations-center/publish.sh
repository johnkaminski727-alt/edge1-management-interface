#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/edge1-management-interface"
SOURCE="$ROOT/src/web/operations-center/index.html"
SNMP_SOURCE="$ROOT/src/web/operations-center/snmp.html"
DEST="/var/www/edge1-status/index.html"
SNMP_DIR="/var/www/edge1-status/operations-center"
SNMP_DEST="$SNMP_DIR/snmp.html"

if [ ! -f "$SOURCE" ]; then
    echo "Missing source: $SOURCE"
    exit 1
fi
if [ ! -f "$SNMP_SOURCE" ]; then
    echo "Missing source: $SNMP_SOURCE"
    exit 1
fi

sudo install -m 0644 "$SOURCE" "$DEST"
sudo install -d -m 0755 "$SNMP_DIR"
sudo install -m 0644 "$SNMP_SOURCE" "$SNMP_DEST"

echo "Published Operations Center:"
echo "$DEST"
echo "$SNMP_DEST"
