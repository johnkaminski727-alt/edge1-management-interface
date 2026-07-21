#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED_ROOT="/opt/edge1-management-interface"
UNIT_SRC="$REPO_ROOT/deploy/systemd/edge1-electrum-watch.service"
UNIT_DST="/etc/systemd/system/edge1-electrum-watch.service"
SERVICE_USER="electrum-watch"
SERVICE_HOME="/var/lib/electrum-watch"
VENV="/opt/electrum-watch"

if [ "${EUID}" -ne 0 ]; then
  echo "install-electrum-watch-service.sh must run as root" >&2
  exit 1
fi

if [ "$REPO_ROOT" != "$EXPECTED_ROOT" ]; then
  echo "Repository must be installed at $EXPECTED_ROOT" >&2
  exit 1
fi

for command in /usr/bin/python3 /bin/systemctl /usr/sbin/useradd /usr/bin/install; do
  test -x "$command" || { echo "Missing required command: $command" >&2; exit 1; }
done

test -f "$UNIT_SRC" || { echo "Missing unit: $UNIT_SRC" >&2; exit 1; }

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$SERVICE_HOME" --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 \
  "$SERVICE_HOME" "$SERVICE_HOME/.electrum" "$SERVICE_HOME/wallets"

if [ ! -x "$VENV/bin/electrum" ]; then
  echo "Electrum is not installed at $VENV/bin/electrum" >&2
  echo "Install and verify the approved Electrum release before enabling this service." >&2
  exit 1
fi

if [ ! -f "$SERVICE_HOME/wallets/wwcx-watch-only" ]; then
  echo "Missing watch-only wallet: $SERVICE_HOME/wallets/wwcx-watch-only" >&2
  echo "Import only an xpub/watch-only wallet as the $SERVICE_USER account." >&2
  exit 1
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_HOME"
chmod 0700 "$SERVICE_HOME" "$SERVICE_HOME/.electrum" "$SERVICE_HOME/wallets"
chmod 0600 "$SERVICE_HOME/wallets/wwcx-watch-only"

install -m 0644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
systemctl enable --now edge1-electrum-watch.service
systemctl --no-pager --full status edge1-electrum-watch.service
