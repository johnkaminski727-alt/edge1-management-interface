#!/bin/sh
set -eu
echo "STOP: retired 2026-10-07. Dyn Standard DNS remains public authoritative; Edge1 publishes through authenticated TSIG/API synchronization. The BIND/AXFR hidden-primary runtime must not be reactivated by this script." >&2
exit 64

ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATE=${EDGE1_HIDDEN_PRIMARY_STATE:-/var/lib/edge1-authoritative-dns}
RUNTIME=${EDGE1_HIDDEN_PRIMARY_RUNTIME:-/var/lib/bind/wwcx-hidden-primary}
LISTEN_V4=${EDGE1_HIDDEN_PRIMARY_LISTEN_V4:-}
LISTEN_V6=${EDGE1_HIDDEN_PRIMARY_LISTEN_V6:-none}
[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }
[ -n "$LISTEN_V4" ] || { echo "STOP: set EDGE1_HIDDEN_PRIMARY_LISTEN_V4 explicitly." >&2; exit 2; }
python3 "$ROOT/tools/dns/validate_hidden_primary_candidate.py" --inventory "$STATE/ww.cx-inventory.json" --zone-file "$STATE/ww.cx.zone"
case "$LISTEN_V4" in *[!0-9.]*|'') echo "STOP: invalid IPv4 listen address" >&2; exit 2;; esac
case "$LISTEN_V6" in none) V6_RENDER='none;' ;; *) V6_RENDER="$LISTEN_V6; ::1;" ;; esac

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="/var/backups/edge1-hidden-primary-$STAMP"
install -d -m 0700 "$BACKUP"
[ ! -e /etc/bind ] || cp -a /etc/bind "$BACKUP/bind-before"

# Prevent Debian package post-install hooks from starting the default broad BIND
# configuration before the hidden-primary config and firewall are in place.
POLICY_CREATED=0
cleanup_policy() { [ "$POLICY_CREATED" -eq 0 ] || rm -f /usr/sbin/policy-rc.d; }
trap cleanup_policy EXIT INT TERM
if ! dpkg-query -W -f='${Status}' bind9 2>/dev/null | grep -q 'install ok installed'; then
  if [ ! -e /usr/sbin/policy-rc.d ]; then
    printf '#!/bin/sh\nexit 101\n' >/usr/sbin/policy-rc.d
    chmod 0755 /usr/sbin/policy-rc.d
    POLICY_CREATED=1
  fi
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y bind9 bind9-utils
  cleanup_policy
  POLICY_CREATED=0
fi

install -d -o bind -g bind -m 0750 "$RUNTIME"
install -o root -g bind -m 0640 "$STATE/ww.cx.zone" "$RUNTIME/ww.cx.zone"
CANON=$(sha256sum "$STATE/ww.cx.zone" | awk '{print $1}')
RUN=$(sha256sum "$RUNTIME/ww.cx.zone" | awk '{print $1}')
[ "$CANON" = "$RUN" ] || { echo "STOP: runtime zone checksum mismatch" >&2; exit 3; }

python3 - "$ROOT/deploy/dns/named-hidden-primary.conf.template" /etc/bind/named.conf "$LISTEN_V4" "$V6_RENDER" <<'PY'
from pathlib import Path
import sys
src,dst,v4,v6=sys.argv[1:]
s=Path(src).read_text().replace('__LISTEN_V4__',v4).replace('__LISTEN_V6__',v6)
Path(dst).write_text(s)
PY
chmod 0644 /etc/bind/named.conf
/usr/sbin/named-checkconf /etc/bind/named.conf
/usr/sbin/named-checkzone ww.cx "$RUNTIME/ww.cx.zone"

install -m 0750 "$ROOT/deploy/dns/edge1-hidden-primary-firewall" /usr/local/sbin/edge1-hidden-primary-firewall
install -m 0644 "$ROOT/deploy/dns/edge1-hidden-primary-firewall.service" /etc/systemd/system/edge1-hidden-primary-firewall.service
systemctl daemon-reload
systemctl enable --now edge1-hidden-primary-firewall.service
systemctl enable named.service >/dev/null 2>&1 || true
systemctl reset-failed named.service || true
systemctl restart named.service
sleep 1
systemctl is-active --quiet named.service || { echo "STOP: named did not become active" >&2; exit 4; }
SOA=$(/usr/bin/dig +time=2 +tries=1 @127.0.0.1 ww.cx SOA +short)
[ -n "$SOA" ] || { echo "STOP: authoritative SOA query failed" >&2; exit 4; }
# Split-DNS safety: BIND must not take the authenticated WireGuard resolver socket.
if /usr/bin/ss -lntup '( sport = :53 )' 2>/dev/null | grep -F '10.77.0.1:53' | grep -Fq 'named'; then
  echo "STOP: named unexpectedly bound the WireGuard DNS address" >&2
  exit 5
fi
WG=$(/usr/bin/dig +time=2 +tries=1 @10.77.0.1 edge1.ww.cx A +short)
[ -n "$WG" ] || { echo "STOP: WireGuard split resolution failed" >&2; exit 5; }

cat >"$STATE/LOCAL_ACTIVE" <<MARKER
activated_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
listen_v4=$LISTEN_V4
candidate_serial=$(printf '%s\n' "$SOA" | awk '{print $3}')
runtime_sha256=$RUN
split_dns_preserved=true
MARKER
chown root:bind "$STATE/LOCAL_ACTIVE"
chmod 0640 "$STATE/LOCAL_ACTIVE"
echo "WW.CX hidden primary active locally. Dyn secondary acceptance remains a separate verification gate."
echo "Backup: $BACKUP"
