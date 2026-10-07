#!/bin/sh
set -eu
ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATE=${EDGE1_HIDDEN_PRIMARY_STATE:-/var/lib/edge1-authoritative-dns}
[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }
install -d -m 0750 -o root -g root "$STATE"
install -m 0640 -o root -g root "$ROOT/config/dns/wwcx-zone-inventory.example.json" "$STATE/ww.cx-inventory.example.json"
rm -f "$STATE/ACTIVATED"
printf '%s\n' 'Hidden-primary candidate workspace prepared. Activation remains blocked until a complete zone inventory and validated zone file are installed.'
