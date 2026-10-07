#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || exit 1
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BK=/var/backups/mail-room-web-$STAMP
mkdir -m 700 "$BK"
cp -a /var/www/mail-room/. "$BK/"
node --check "$REPO/src/web/mail-room/app.js"
for f in app.js styles.css index.html; do
  install -m 0644 "$REPO/src/web/mail-room/$f" "/var/www/mail-room/$f.new"
  mv "/var/www/mail-room/$f.new" "/var/www/mail-room/$f"
done
printf 'Mail Room website published; backup: %s\n' "$BK"
