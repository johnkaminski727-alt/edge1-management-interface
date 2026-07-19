#!/bin/sh
set -eu

# LOOPBACK-ONLY staging installer.
# Default mode is a dry run. Use --apply to install only the localhost numbering
# service. This script does not change DNS, nftables, Apache, FreePBX, Asterisk,
# certificates, or any public listener.

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
MODE=${1:-}
STAMP=$(date +%Y%m%d-%H%M%S)
EVIDENCE="/var/lib/wwcx-interconnect-staging/evidence/$STAMP"
UNIT_SRC="$ROOT/deploy/wwcx-numbering-node.service"
UNIT_DST="/etc/systemd/system/wwcx-numbering-node.service"

say() { printf '%s\n' "$*"; }
fail() { printf 'install failed: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail 'run with sudo'
[ -s "$ROOT/server/wwcx_numbering_node.py" ] || fail 'numbering service source missing'
[ -s "$UNIT_SRC" ] || fail 'systemd unit missing'

say 'WW.CX loopback staging preflight'
say 'Planned listener: 127.0.0.1:8093'
say 'Public firewall changes: none'
say 'Asterisk/FreePBX changes: none'
say 'Kamailio activation: not performed by this installer'

if ss -lnt | grep -E '127\.0\.0\.1:8093|0\.0\.0\.0:8093|\[::\]:8093' >/dev/null 2>&1; then
  fail 'TCP port 8093 is already in use'
fi

"$ROOT/deploy/interconnect/validate-staging-assets.sh"
python3 -m unittest "$ROOT/tests/test_wwcx_numbering_node.py"

if [ "$MODE" != "--apply" ]; then
  say 'Dry run passed. No files or services were changed.'
  say 'Run with --apply only after reviewing this output.'
  exit 0
fi

install -d -o root -g root -m 0755 /var/lib/wwcx-interconnect-staging
install -d -o root -g root -m 0755 "$EVIDENCE"
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/wwcx-numbering-node

{
  date --iso-8601=seconds
  uname -a
  ss -lntup | grep -E ':(5060|5061|5070|8093)([[:space:]]|$)' || true
  sha256sum "$ROOT/server/wwcx_numbering_node.py" "$UNIT_SRC"
} >"$EVIDENCE/baseline.txt"

if [ -e "$UNIT_DST" ]; then
  cp -a "$UNIT_DST" "$EVIDENCE/wwcx-numbering-node.service.previous"
fi

install -o root -g root -m 0644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
systemctl enable --now wwcx-numbering-node.service

sleep 1
systemctl is-active --quiet wwcx-numbering-node.service || {
  journalctl -u wwcx-numbering-node.service -n 50 --no-pager >"$EVIDENCE/failure-journal.txt" 2>&1 || true
  systemctl disable --now wwcx-numbering-node.service >/dev/null 2>&1 || true
  if [ -e "$EVIDENCE/wwcx-numbering-node.service.previous" ]; then
    cp -a "$EVIDENCE/wwcx-numbering-node.service.previous" "$UNIT_DST"
  else
    rm -f "$UNIT_DST"
  fi
  systemctl daemon-reload
  fail "numbering service failed; rollback completed; evidence: $EVIDENCE"
}

ss -lnt | grep -F '127.0.0.1:8093' >/dev/null || fail 'service is not bound to 127.0.0.1:8093'
if ss -lnt | grep -E '0\.0\.0\.0:8093|\[::\]:8093' >/dev/null; then
  systemctl disable --now wwcx-numbering-node.service >/dev/null 2>&1 || true
  fail 'unsafe non-loopback listener detected; service stopped'
fi

curl -fsS http://127.0.0.1:8093/healthz >"$EVIDENCE/healthz.json"
systemctl status wwcx-numbering-node.service --no-pager >"$EVIDENCE/service-status.txt" 2>&1 || true
ss -lntup | grep -E ':(5060|5061|5070|8093)([[:space:]]|$)' >"$EVIDENCE/listeners-after.txt" || true

say "Loopback numbering staging installed successfully."
say "Evidence: $EVIDENCE"
say 'No DNS, firewall, Apache, certificate, FreePBX, Asterisk, or public listener changes were made.'
