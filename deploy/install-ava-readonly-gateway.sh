#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="/opt/bigbird-ai-gateway"
UNIT="/etc/systemd/system/bigbird-ai-gateway.service"

if [ "${EUID}" -ne 0 ]; then
  echo "install-ava-readonly-gateway.sh must run as root" >&2
  exit 1
fi

test -f "$ROOT/services/bigbird-ai-gateway/app/main.py"
test -f "$ROOT/services/bigbird-ai-gateway/app/library_engine.py"
test -f "$ROOT/deploy/systemd/bigbird-ai-gateway.service"
test -f /etc/edge1-operations-api.secret

if ! getent group bigbird-ai >/dev/null; then
  groupadd --system bigbird-ai
fi
if ! getent passwd bigbird-ai >/dev/null; then
  useradd --system --gid bigbird-ai --home-dir /nonexistent --shell /usr/sbin/nologin bigbird-ai
fi

install -d -m 0755 "$RUNTIME" "$RUNTIME/app"
install -m 0644 "$ROOT/services/bigbird-ai-gateway/app/__init__.py" "$RUNTIME/app/__init__.py"
install -m 0644 "$ROOT/services/bigbird-ai-gateway/app/library_engine.py" "$RUNTIME/app/library_engine.py"
install -m 0644 "$ROOT/services/bigbird-ai-gateway/app/main.py" "$RUNTIME/app/main.py"
chown -R root:root "$RUNTIME"

install -m 0644 "$ROOT/deploy/systemd/bigbird-ai-gateway.service" "$UNIT"

install -d -m 0750 /etc
if [ ! -f /etc/bigbird-ai-gateway.env ]; then
  secret="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  cat > /etc/bigbird-ai-gateway.env <<EOF
BB_RELAY_KEY_ID=edge1-ava-rebuild
BB_RELAY_SECRET=$secret
BB_OPENAI_MODEL=gpt-5-mini
EOF
  chown root:bigbird-ai /etc/bigbird-ai-gateway.env
  chmod 0640 /etc/bigbird-ai-gateway.env
fi

systemctl daemon-reload
systemctl enable --now bigbird-ai-gateway.service

echo "Installed read-only Ava gateway at 127.0.0.1:8787"
echo "Model credential is intentionally not created by this installer."
