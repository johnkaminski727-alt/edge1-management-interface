#!/usr/bin/env bash
set -euo pipefail

SERVICE_USER="electrum-watch"
SERVICE_HOME="/var/lib/electrum-watch"
ELECTRUM="/opt/electrum-watch/bin/electrum"
RPC_PORT="${ELECTRUM_RPC_PORT:-7777}"

if [ "${EUID}" -ne 0 ]; then
  echo "configure-electrum-watch-rpc.sh must run as root" >&2
  exit 1
fi

test -x "$ELECTRUM" || { echo "Missing $ELECTRUM" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Missing service user $SERVICE_USER" >&2; exit 1; }

case "$RPC_PORT" in
  ''|*[!0-9]*) echo "ELECTRUM_RPC_PORT must be numeric" >&2; exit 1 ;;
esac
if [ "$RPC_PORT" -lt 1024 ] || [ "$RPC_PORT" -gt 65535 ]; then
  echo "ELECTRUM_RPC_PORT must be between 1024 and 65535" >&2
  exit 1
fi

RPC_USER="wwcx-electrum"
RPC_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(36))
PY
)"

run_electrum() {
  sudo -u "$SERVICE_USER" env HOME="$SERVICE_HOME" ELECTRUMDIR="$SERVICE_HOME/.electrum" \
    "$ELECTRUM" "$@"
}

run_electrum setconfig rpchost 127.0.0.1
run_electrum setconfig rpcport "$RPC_PORT"
run_electrum setconfig rpcuser "$RPC_USER"
run_electrum setconfig rpcpassword "$RPC_PASSWORD"

install -d -o root -g "$SERVICE_USER" -m 0750 /etc/electrum-watch
umask 077
cat > /etc/electrum-watch/rpc.env <<EOF
ELECTRUM_RPC_HOST=127.0.0.1
ELECTRUM_RPC_PORT=$RPC_PORT
ELECTRUM_RPC_USER=$RPC_USER
ELECTRUM_RPC_PASSWORD=$RPC_PASSWORD
EOF
chown root:"$SERVICE_USER" /etc/electrum-watch/rpc.env
chmod 0640 /etc/electrum-watch/rpc.env

unset RPC_PASSWORD

echo "Electrum RPC configured for localhost:$RPC_PORT"
echo "Credentials stored root-owned at /etc/electrum-watch/rpc.env"
