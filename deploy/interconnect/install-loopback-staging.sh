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
APPLIED=0
PREVIOUS_UNIT=0

say() { printf '%s\n' "$*"; }
fail() { printf 'install failed: %s\n' "$1" >&2; exit 1; }

case "$MODE" in
  ""|--apply) ;;
  *) fail "unknown argument: $MODE" ;;
esac

[ "$(id -u)" -eq 0 ] || fail 'run with sudo'
[ -s "$ROOT/server/wwcx_numbering_node.py" ] || fail 'numbering service source missing'
[ -s "$UNIT_SRC" ] || fail 'systemd unit missing'

say 'WW.CX loopback staging preflight'
say 'Planned listener: 127.0.0.1:8093'
say 'Public firewall changes: none'
say 'Asterisk/FreePBX changes: none'
say 'Kamailio activation: not performed by this installer'

if ss -lnt | grep -E '0\.0\.0\.0:8093|\[::\]:8093' >/dev/null 2>&1; then
  fail 'unsafe non-loopback TCP listener already uses port 8093'
fi
if ss -lnt | grep -F '127.0.0.1:8093' >/dev/null 2>&1; then
  if systemctl is-active --quiet wwcx-numbering-node.service; then
    say 'Existing loopback numbering service detected; install may update its unit.'
  else
    fail 'TCP port 8093 is in use by an unexpected process'
  fi
fi

"$ROOT/deploy/interconnect/validate-staging-assets.sh"
python3 -m unittest discover -s "$ROOT/tests" -p 'test_wwcx_numbering_node.py'

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
  PREVIOUS_UNIT=1
fi

rollback() {
  reason=$1
  journalctl -u wwcx-numbering-node.service -n 100 --no-pager \
    >"$EVIDENCE/failure-journal.txt" 2>&1 || true
  systemctl disable --now wwcx-numbering-node.service >/dev/null 2>&1 || true
  if [ "$PREVIOUS_UNIT" -eq 1 ]; then
    cp -a "$EVIDENCE/wwcx-numbering-node.service.previous" "$UNIT_DST"
    systemctl daemon-reload
    systemctl enable --now wwcx-numbering-node.service >/dev/null 2>&1 || true
  else
    rm -f "$UNIT_DST"
    systemctl daemon-reload
  fi
  APPLIED=0
  fail "$reason; rollback completed; evidence: $EVIDENCE"
}

on_exit() {
  status=$?
  if [ "$status" -ne 0 ] && [ "$APPLIED" -eq 1 ]; then
    rollback "unexpected installer failure (exit $status)"
  fi
  exit "$status"
}

trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 129' HUP
trap 'exit 143' TERM

install -o root -g root -m 0644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
APPLIED=1
systemctl enable wwcx-numbering-node.service >/dev/null
systemctl restart wwcx-numbering-node.service

ready=0
attempt=0
while [ "$attempt" -lt 20 ]; do
  if systemctl is-active --quiet wwcx-numbering-node.service && \
     curl -fsS http://127.0.0.1:8093/healthz >"$EVIDENCE/healthz.json.tmp" 2>/dev/null; then
    ready=1
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done

[ "$ready" -eq 1 ] || rollback 'numbering service did not become healthy within 20 seconds'
mv "$EVIDENCE/healthz.json.tmp" "$EVIDENCE/healthz.json"

ss -lnt | grep -F '127.0.0.1:8093' >/dev/null || rollback 'service is not bound to 127.0.0.1:8093'
if ss -lnt | grep -E '0\.0\.0\.0:8093|\[::\]:8093' >/dev/null; then
  rollback 'unsafe non-loopback listener detected'
fi

systemctl status wwcx-numbering-node.service --no-pager >"$EVIDENCE/service-status.txt" 2>&1 || true
ss -lntup | grep -E ':(5060|5061|5070|8093)([[:space:]]|$)' >"$EVIDENCE/listeners-after.txt" || true
python3 "$ROOT/server/wwcx_numbering_node.py" \
  --database /var/lib/wwcx-numbering-node/numbering.sqlite3 \
  list-sources >"$EVIDENCE/numbering-sources.json"

APPLIED=0
trap - EXIT HUP INT TERM
say 'Loopback numbering staging installed successfully.'
say "Evidence: $EVIDENCE"
say 'No DNS, firewall, Apache, certificate, FreePBX, Asterisk, or public listener changes were made.'
