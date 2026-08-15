#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CONFIG="$ROOT/modules/time-authority/config/edge1-chrony.conf"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

command -v python3 >/dev/null 2>&1 || fail "python3 is required"
command -v systemctl >/dev/null 2>&1 || fail "systemctl is required"
command -v ss >/dev/null 2>&1 || fail "ss is required"
command -v getent >/dev/null 2>&1 || fail "getent is required"
command -v apt-cache >/dev/null 2>&1 || fail "apt-cache is required"

[ -r "$CONFIG" ] || fail "missing chrony configuration: $CONFIG"

python3 "$ROOT/tests/validate_time_authority_ntp_server.py"

if ss -lun 2>/dev/null | awk '{print $5}' | grep -Eq '(^|\]):?123$|(^|:)123$'; then
    echo "Existing UDP/123 listener detected:"
    ss -lunp 2>/dev/null | grep -E '(^|[[:space:]])[^[:space:]]*:123([[:space:]]|$)' || true
    fail "UDP/123 must be reviewed before NTP server cutover"
fi

echo "PASS: UDP/123 is currently free."

if systemctl is-active --quiet systemd-timesyncd.service; then
    echo "PASS: systemd-timesyncd is currently active and will remain untouched by preflight."
else
    echo "NOTICE: systemd-timesyncd is not active; review the current clock discipline service before cutover."
fi

if apt-cache show chrony >/dev/null 2>&1; then
    echo "PASS: chrony is available from configured APT repositories."
else
    fail "chrony package is not available from configured APT repositories"
fi

for host in sth1.ntp.se sth2.ntp.se mmo1.ntp.se time.nist.gov time.cloudflare.com; do
    if getent ahostsv4 "$host" >/dev/null 2>&1; then
        echo "PASS: resolves $host"
    else
        fail "cannot resolve upstream NTP source $host"
    fi
done

echo
systemctl status systemd-timesyncd.service --no-pager 2>/dev/null || true
echo
if command -v timedatectl >/dev/null 2>&1; then
    timedatectl status || true
fi

echo
printf '%s\n' "WW.CX public NTP server preflight passed." \
    "No package, clock-service, firewall, DNS, or listener changes were made."
