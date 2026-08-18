#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
MODE=${1:-}
SERVICE=edge1-secure-mcp-tunnel.service
ETC_DIR=/etc/edge1-tunnel
LIBEXEC_DIR=/usr/local/libexec/edge1-tunnel
UNIT=/etc/systemd/system/$SERVICE
BINARY=/usr/local/bin/tunnel-client

[ "$(id -u)" -eq 0 ] || { echo "run with sudo/root" >&2; exit 1; }
id edge1-operator >/dev/null 2>&1 || { echo "edge1-operator account missing" >&2; exit 2; }
[ -x "$BINARY" ] || { echo "install the official tunnel-client release at $BINARY first" >&2; exit 3; }
"$BINARY" cloudflared version >/dev/null 2>&1 || {
    echo "tunnel-client companion runtime unavailable; install the complete official release bundle" >&2
    exit 4
}

python3 - "$ROOT/deploy/edge1-tunnel/tunnel-client.yaml" <<'PY'
from pathlib import Path
p = Path(__import__('sys').argv[1])
text = p.read_text(encoding='utf-8')
required = (
    'url: http://127.0.0.1:8102/mcp',
    'Authorization: env:EDGE1_MCP_AUTHORIZATION',
    'api_key: file:/etc/edge1-tunnel/runtime-api-key',
    'listen_addr: 127.0.0.1:0',
    'managed: true',
)
for token in required:
    if token not in text:
        raise SystemExit(f'missing required tunnel config token: {token}')
PY

case "$MODE" in
    "")
        echo "Dry run passed. No files changed."
        echo "Use --apply to stage the disabled tunnel service after the complete tunnel-client release is installed."
        exit 0
        ;;
    --apply) ;;
    *) echo "unknown argument: $MODE" >&2; exit 5 ;;
esac

install -d -o root -g edge1-operator -m 0750 "$ETC_DIR"
install -d -o root -g root -m 0755 "$LIBEXEC_DIR"
install -o root -g edge1-operator -m 0640 \
    "$ROOT/deploy/edge1-tunnel/tunnel-client.yaml" \
    "$ETC_DIR/tunnel-client.yaml"
install -o root -g root -m 0755 \
    "$ROOT/deploy/edge1-tunnel/edge1-secure-mcp-tunnel.sh" \
    "$LIBEXEC_DIR/edge1-secure-mcp-tunnel.sh"
install -o root -g root -m 0644 \
    "$ROOT/deploy/edge1-tunnel/edge1-secure-mcp-tunnel.service" \
    "$UNIT"

systemctl daemon-reload
systemctl disable "$SERVICE" >/dev/null 2>&1 || true
systemctl stop "$SERVICE" >/dev/null 2>&1 || true
systemd-analyze verify "$UNIT"

[ ! -e "$ETC_DIR/runtime-api-key" ] || {
    owner=$(stat -c '%U:%G' "$ETC_DIR/runtime-api-key")
    mode=$(stat -c '%a' "$ETC_DIR/runtime-api-key")
    [ "$owner" = root:edge1-operator ] && [ "$mode" = 640 ] || {
        echo "existing runtime-api-key has unexpected owner/mode: $owner $mode" >&2
        exit 6
    }
}

[ ! -e "$ETC_DIR/tunnel-id" ] || {
    owner=$(stat -c '%U:%G' "$ETC_DIR/tunnel-id")
    mode=$(stat -c '%a' "$ETC_DIR/tunnel-id")
    [ "$owner" = root:edge1-operator ] && [ "$mode" = 640 ] || {
        echo "existing tunnel-id has unexpected owner/mode: $owner $mode" >&2
        exit 7
    }
}

if systemctl is-enabled --quiet "$SERVICE" 2>/dev/null; then
    echo "refusing: tunnel service unexpectedly enabled" >&2
    exit 8
fi
if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
    echo "refusing: tunnel service unexpectedly active" >&2
    exit 9
fi

echo "Secure MCP Tunnel assets staged; service remains disabled/inactive."
echo "Credential/account enrollment is still required before doctor/start."
