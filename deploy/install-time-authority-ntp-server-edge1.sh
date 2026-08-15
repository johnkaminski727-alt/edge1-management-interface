#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CONFIG="$ROOT/modules/time-authority/config/edge1-chrony.conf"
EVIDENCE_ROOT=${WWCX_NTP_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/public-ntp-server}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/cutover-$STAMP"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

udp123_listener_present() {
    ss -H -lun 'sport = :123' 2>/dev/null | grep -q .
}

[ "$(id -u)" -eq 0 ] || fail "run with sudo/root"
[ "${WWCX_NTP_APPROVE_CLOCK_DAEMON_CUTOVER:-}" = "YES" ] || \
    fail "set WWCX_NTP_APPROVE_CLOCK_DAEMON_CUTOVER=YES after explicit approval to replace systemd-timesyncd with chronyd"
[ "${WWCX_NTP_APPROVE_PUBLIC_UDP123:-}" = "YES" ] || \
    fail "set WWCX_NTP_APPROVE_PUBLIC_UDP123=YES after explicit approval to expose the NTP daemon on UDP/123"

sh "$ROOT/deploy/time-authority-ntp-server-edge1-preflight.sh"

install -d -m 0750 "$EVIDENCE_DIR"

{
    echo "timestamp_utc=$STAMP"
    echo "repo_root=$ROOT"
    printf 'repo_head='
    git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown
    uname -a
} > "$EVIDENCE_DIR/install-metadata.txt"

(systemctl cat systemd-timesyncd.service 2>&1 || true) > "$EVIDENCE_DIR/systemd-timesyncd-before.txt"
(systemctl status systemd-timesyncd.service --no-pager 2>&1 || true) > "$EVIDENCE_DIR/systemd-timesyncd-status-before.txt"
(ss -lunp 2>&1 || true) > "$EVIDENCE_DIR/udp-listeners-before.txt"
(timedatectl status 2>&1 || true) > "$EVIDENCE_DIR/timedatectl-before.txt"
(dpkg-query -W -f='${Package}\t${Version}\t${Status}\n' chrony systemd-timesyncd 2>&1 || true) > "$EVIDENCE_DIR/time-packages-before.txt"

if [ -f /etc/chrony/chrony.conf ]; then
    cp -a /etc/chrony/chrony.conf "$EVIDENCE_DIR/chrony.conf.before"
fi
if [ -f /etc/systemd/timesyncd.conf ]; then
    cp -a /etc/systemd/timesyncd.conf "$EVIDENCE_DIR/timesyncd.conf.before"
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y chrony

# Prevent two services from attempting to discipline the same system clock.
systemctl disable --now systemd-timesyncd.service 2>/dev/null || true

install -d -m 0755 /etc/chrony
install -m 0644 "$CONFIG" /etc/chrony/chrony.conf

systemctl enable chrony.service
systemctl restart chrony.service

# Wait up to about one minute for a valid selected source.
if ! chronyc waitsync 30 0 0 2; then
    systemctl status chrony.service --no-pager || true
    chronyc tracking || true
    chronyc sources -v || true
    fail "chronyd did not synchronize within the acceptance window; rollback evidence is in $EVIDENCE_DIR"
fi

sh "$ROOT/deploy/time-authority-ntp-server-edge1-smoke-test.sh"

(systemctl status chrony.service --no-pager 2>&1 || true) > "$EVIDENCE_DIR/chrony-status-after.txt"
(chronyc tracking 2>&1 || true) > "$EVIDENCE_DIR/chrony-tracking-after.txt"
(chronyc sources -v 2>&1 || true) > "$EVIDENCE_DIR/chrony-sources-after.txt"
(ss -lunp 2>&1 || true) > "$EVIDENCE_DIR/udp-listeners-after.txt"
(timedatectl status 2>&1 || true) > "$EVIDENCE_DIR/timedatectl-after.txt"
(dpkg-query -W -f='${Package}\t${Version}\t${Status}\n' chrony systemd-timesyncd 2>&1 || true) > "$EVIDENCE_DIR/time-packages-after.txt"

if systemctl is-active --quiet systemd-timesyncd.service; then
    fail "systemd-timesyncd is still active; refusing dual clock discipline"
fi

if ! systemctl is-active --quiet chrony.service; then
    fail "chrony.service is not active"
fi

if ! udp123_listener_present; then
    fail "chronyd is not listening on UDP/123"
fi

echo "WW.CX Edge1 NTP daemon installed and locally verified."
echo "Rollback evidence: $EVIDENCE_DIR"
echo "DNS publication and perimeter firewall exposure must be handled as separate approved production changes."
