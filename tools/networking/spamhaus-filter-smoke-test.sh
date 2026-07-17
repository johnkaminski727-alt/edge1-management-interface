#!/usr/bin/env bash
set -euo pipefail

NFT="${NFT:-/usr/sbin/nft}"
STATE_DIR="${BB_SPAMHAUS_STATE_DIR:-/var/lib/bigbird-networking/spamhaus}"

if [ "${EUID}" -ne 0 ]; then
  echo "spamhaus-filter-smoke-test.sh must run as root" >&2
  exit 1
fi

"$NFT" list table inet bigbird_spamhaus >/dev/null
test -s "$STATE_DIR/spamhaus.nft"
test -s "$STATE_DIR/summary.txt"

echo "Spamhaus table is installed:"
"$NFT" list table inet bigbird_spamhaus | sed -n '1,80p'

echo
echo "Last update summary:"
cat "$STATE_DIR/summary.txt"

echo
systemctl --no-pager --full status bigbird-spamhaus-filter.service || true
systemctl --no-pager list-timers bigbird-spamhaus-filter.timer || true
