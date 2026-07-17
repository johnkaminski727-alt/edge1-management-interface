#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_SRC="$REPO_ROOT/tools/networking/systemd/bigbird-spamhaus-filter.service"
TIMER_SRC="$REPO_ROOT/tools/networking/systemd/bigbird-spamhaus-filter.timer"
SERVICE_DST="/etc/systemd/system/bigbird-spamhaus-filter.service"
TIMER_DST="/etc/systemd/system/bigbird-spamhaus-filter.timer"

if [ "${EUID}" -ne 0 ]; then
  echo "install-spamhaus-filter.sh must run as root" >&2
  exit 1
fi

for command in /usr/sbin/nft /usr/bin/curl /usr/bin/python3 /bin/systemctl; do
  if [ ! -x "$command" ]; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

install -m 0755 "$REPO_ROOT/tools/networking/spamhaus-nft-update.sh" /usr/local/sbin/bigbird-spamhaus-nft-update
install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
install -m 0644 "$TIMER_SRC" "$TIMER_DST"

systemctl daemon-reload
systemctl enable --now bigbird-spamhaus-filter.timer
systemctl start bigbird-spamhaus-filter.service
systemctl --no-pager --full status bigbird-spamhaus-filter.service
systemctl --no-pager list-timers bigbird-spamhaus-filter.timer
