#!/bin/sh
set -eu
MODE=dry-run
[ "${1:-}" = "--apply" ] && MODE=apply
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
VERSION=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf source)
TARGET="/opt/wwcx-ava-operator-broker/releases/$VERSION"
printf 'mode=%s\nsource=%s\ntarget=%s\n' "$MODE" "$ROOT" "$TARGET"
[ "$MODE" = apply ] || exit 0
install -d -m 0755 /opt/wwcx-ava-operator-broker/releases /etc/ava-operator /var/log/wwcx-ava-operator-broker
if [ ! -f /etc/ava-operator/broker-token ]; then
  umask 077
  python3 -c 'import secrets; print(secrets.token_hex(32))' > /etc/ava-operator/broker-token
fi
chown root:bigbird-ai /etc/ava-operator/broker-token
chmod 0640 /etc/ava-operator/broker-token
rm -rf "$TARGET"
install -d -m 0755 "$TARGET/server" "$TARGET/config"
install -m 0644 "$ROOT/server/ava_operator_broker.py" "$TARGET/server/ava_operator_broker.py"
install -m 0644 "$ROOT/server/ava_operator_policy.py" "$TARGET/server/ava_operator_policy.py"
install -m 0644 "$ROOT/config/ava-operator-parity.json" "$TARGET/config/ava-operator-parity.json"
ln -sfn "$TARGET" /opt/wwcx-ava-operator-broker/current
install -m 0644 "$ROOT/deploy/ava-operator-broker/wwcx-ava-operator-broker.service" /etc/systemd/system/wwcx-ava-operator-broker.service
systemctl daemon-reload
systemctl enable --now wwcx-ava-operator-broker.service
i=0
until curl -fsS http://127.0.0.1:8118/healthz; do
  i=$((i + 1))
  [ "$i" -ge 20 ] && exit 1
  sleep 0.25
done
