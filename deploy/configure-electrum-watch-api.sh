#!/usr/bin/env bash
set -euo pipefail

SERVICE_USER="electrum-watch"
CONFIG_DIR="/etc/electrum-watch"
CONFIG_FILE="$CONFIG_DIR/api.env"

if [ "${EUID}" -ne 0 ]; then
  echo "configure-electrum-watch-api.sh must run as root" >&2
  exit 1
fi

id "$SERVICE_USER" >/dev/null 2>&1 || {
  echo "Missing service user: $SERVICE_USER" >&2
  exit 1
}

API_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

install -d -o root -g "$SERVICE_USER" -m 0750 "$CONFIG_DIR"
umask 077
cat > "$CONFIG_FILE" <<EOF
ELECTRUM_API_TOKEN=$API_TOKEN
EOF
chown root:"$SERVICE_USER" "$CONFIG_FILE"
chmod 0640 "$CONFIG_FILE"
unset API_TOKEN

echo "Electrum watch API token configured at $CONFIG_FILE"
echo "The token was not printed. Transfer it only through an approved secret channel."
