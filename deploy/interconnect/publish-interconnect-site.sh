#!/bin/sh
set -eu

# Stages the public information site only. It does not enable Apache, issue
# certificates, change DNS, alter firewall policy, or activate SIP service.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SOURCE="$ROOT/src/web/interconnect"
DEST=${DEST:-/var/www/interconnect.ww.cx}

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
test -s "$SOURCE/index.html"
test -s "$SOURCE/service.json"

install -d -o root -g www-data -m 0755 "$DEST"
install -o root -g www-data -m 0644 "$SOURCE/index.html" "$DEST/index.html"
install -o root -g www-data -m 0644 "$SOURCE/service.json" "$DEST/service.json"

printf '%s\n' "Staged WW.CX interconnect information site at $DEST"
printf '%s\n' "No Apache configuration, certificate, DNS, firewall, or SIP listener was changed."
