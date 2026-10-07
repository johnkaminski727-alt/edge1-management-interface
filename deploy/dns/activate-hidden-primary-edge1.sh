#!/bin/sh
set -eu
ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATE=${EDGE1_HIDDEN_PRIMARY_STATE:-/var/lib/edge1-authoritative-dns}
LISTEN_V4=${EDGE1_HIDDEN_PRIMARY_LISTEN_V4:-}
LISTEN_V6=${EDGE1_HIDDEN_PRIMARY_LISTEN_V6:-none}
[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }
[ -n "$LISTEN_V4" ] || { echo "STOP: set EDGE1_HIDDEN_PRIMARY_LISTEN_V4 explicitly." >&2; exit 2; }
python3 "$ROOT/tools/dns/validate_hidden_primary_candidate.py" --inventory "$STATE/ww.cx-inventory.json" --zone-file "$STATE/ww.cx.zone"
case "$LISTEN_V4" in *[!0-9.]*|'') echo "STOP: invalid IPv4 listen address" >&2; exit 2;; esac
case "$LISTEN_V6" in none) V6_RENDER='::1;' ;; *) V6_RENDER="$LISTEN_V6; ::1;" ;; esac
install -d -m 0750 "$STATE/cache"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="/var/backups/edge1-hidden-primary-$STAMP"
install -d -m 0700 "$BACKUP"
for p in /etc/bind/named.conf /etc/bind/named.conf.options /etc/bind/named.conf.local; do [ ! -e "$p" ] || cp -a "$p" "$BACKUP/"; done
if ! dpkg-query -W -f='${Status}' bind9 2>/dev/null | grep -q 'install ok installed'; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y bind9 bind9-utils
fi
python3 - "$ROOT/deploy/dns/named-hidden-primary.conf.template" /etc/bind/named.conf "$LISTEN_V4" "$V6_RENDER" <<'PY'
from pathlib import Path
import sys
src,dst,v4,v6=sys.argv[1:]
s=Path(src).read_text().replace('__LISTEN_V4__',v4).replace('__LISTEN_V6__',v6)
Path(dst).write_text(s)
PY
/usr/sbin/named-checkconf /etc/bind/named.conf
/usr/sbin/named-checkzone ww.cx "$STATE/ww.cx.zone"
# Firewall activation is intentionally separate: only Dyn's documented transfer
# addresses should be permitted to TCP/UDP 53 on the hidden-primary address.
echo "STOP-SAFE: BIND configuration validated but service/firewall were not activated automatically."
echo "Validated config: /etc/bind/named.conf"
echo "Backup: $BACKUP"
echo "Next gate: apply source-restricted TCP/UDP 53 firewall rules, then start bind9 after Dyn secondary-zone configuration is ready."
