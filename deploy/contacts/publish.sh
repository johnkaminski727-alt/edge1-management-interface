#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo "STOP: publish requires root" >&2; exit 1; }
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
DEST=/var/www/contacts
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BK=/var/backups/contacts-web-$STAMP
mkdir -m 700 "$BK"
cp -a "$DEST/." "$BK/"
node --check "$REPO/src/web/contacts/app.js"
for f in app.js styles.css index.html; do
  install -m 0644 "$REPO/src/web/contacts/$f" "$DEST/$f.new"
  mv "$DEST/$f.new" "$DEST/$f"
done
printf 'Contacts website published; backup: %s\n' "$BK"
