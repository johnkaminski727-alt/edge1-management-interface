#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/edge1-management-interface"
SOURCE="$ROOT/src/web/operations-center/index.html"
SNMP_SOURCE="$ROOT/src/web/operations-center/snmp.html"
DEST="/var/www/edge1-status/index.html"
SNMP_DIR="/var/www/edge1-status/operations-center"
SNMP_DEST="$SNMP_DIR/snmp.html"
BACKUP_ROOT="/var/backups/edge1-operations-center"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
TMP_INDEX="$(mktemp)"
TMP_SNMP="$(mktemp)"
trap 'rm -f "$TMP_INDEX" "$TMP_SNMP"' EXIT

if [ ! -f "$SOURCE" ]; then
    echo "Missing source: $SOURCE"
    exit 1
fi
if [ ! -f "$SNMP_SOURCE" ]; then
    echo "Missing authenticated SNMP console source: $SNMP_SOURCE"
    exit 1
fi

# The full SNMP console is served only through the authenticated Edge1 operator
# adapter. Never publish that source into the public /edge1-status tree.
sed 's#/edge1-status/operations-center/snmp.html#/edge1-ops/snmp/#g' "$SOURCE" > "$TMP_INDEX"
cat > "$TMP_SNMP" <<'EOF'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>SNMP Operations | WW.CX Edge1</title></head>
<body><main><h1>SNMP Operations</h1><p>This operator console requires an authenticated Edge1 session.</p><p><a href="/edge1-ops/snmp/">Open authenticated SNMP Operations</a></p></main></body></html>
EOF

sudo install -d -m 0700 "$BACKUP_DIR"
if [ -f "$DEST" ]; then sudo cp -a "$DEST" "$BACKUP_DIR/index.html"; fi
if [ -f "$SNMP_DEST" ]; then sudo cp -a "$SNMP_DEST" "$BACKUP_DIR/snmp.html"; fi

sudo install -m 0644 "$TMP_INDEX" "$DEST"
sudo install -d -m 0755 "$SNMP_DIR"
sudo install -m 0644 "$TMP_SNMP" "$SNMP_DEST"

echo "Published Operations Center with authenticated SNMP handoff:"
echo "$DEST"
echo "$SNMP_DEST"
echo "Backup: $BACKUP_DIR"
