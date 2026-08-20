#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
MODE=${1:-}
SERVICE=business159-secure-mcp-tunnel.service
SERVICE_USER=business159-operator
ETC_DIR=/etc/business159-tunnel
SSH_DIR=/etc/business159-operator
STATE_DIR=/var/lib/business159-operator
LIBEXEC_DIR=/usr/local/libexec/business159-tunnel
UNIT=/etc/systemd/system/$SERVICE
BINARY=/usr/local/bin/tunnel-client
MCP_ROOT=$ROOT/tools/mcp/business159-live-shell
NODE_BIN=${BUSINESS159_NODE_BIN:-/usr/bin/node}

[ "$(id -u)" -eq 0 ] || { echo "run with sudo/root" >&2; exit 1; }
[ -x "$BINARY" ] || { echo "official tunnel-client binary unavailable at $BINARY" >&2; exit 2; }
[ -x "$NODE_BIN" ] || { echo "Node runtime unavailable at $NODE_BIN" >&2; exit 3; }
node_major=$($NODE_BIN -p 'process.versions.node.split(".")[0]')
[ "$node_major" -ge 20 ] || { echo "Node >=20 required at $NODE_BIN" >&2; exit 4; }
[ -r "$MCP_ROOT/package.json" ] && [ -r "$MCP_ROOT/src/index.js" ] || { echo "business159-live-shell source unavailable" >&2; exit 5; }

VERSION_LINE=$($BINARY --version 2>/dev/null || true)
[ -n "$VERSION_LINE" ] || { echo "unable to identify tunnel-client version" >&2; exit 6; }
$BINARY run --help 2>&1 | grep -q -- '--mcp.command' || { echo "tunnel-client lacks stdio --mcp.command support" >&2; exit 7; }
$BINARY doctor --help 2>&1 | grep -q -- '--mcp.command' || { echo "tunnel-client doctor lacks stdio --mcp.command support" >&2; exit 8; }

python3 - "$ROOT/deploy/business159-tunnel/tunnel-client.yaml" "$ROOT/deploy/business159-tunnel/business159-secure-mcp-tunnel.sh" <<'PY'
from pathlib import Path
import sys
config = Path(sys.argv[1]).read_text(encoding='utf-8')
wrapper = Path(sys.argv[2]).read_text(encoding='utf-8')
for token in (
    'api_key: file:/etc/business159-tunnel/runtime-api-key',
    'listen_addr: 127.0.0.1:0',
    'url_file: /run/business159-secure-mcp-tunnel/health-url',
    'pid_file: /run/business159-secure-mcp-tunnel/tunnel-client.pid',
):
    if token not in config:
        raise SystemExit(f'missing required Business159 tunnel config token: {token}')
if 'server_urls:' in config or 'commands:' in config:
    raise SystemExit('Business159 stdio binding must be supplied through --mcp.command')
if '--mcp.command "$MCP_COMMAND"' not in wrapper:
    raise SystemExit('Business159 runtime wrapper does not bind stdio MCP with --mcp.command')
PY

if id "$SERVICE_USER" >/dev/null 2>&1; then
    home=$(getent passwd "$SERVICE_USER" | awk -F: '{print $6}')
    shell=$(getent passwd "$SERVICE_USER" | awk -F: '{print $7}')
    [ "$home" = "$STATE_DIR" ] || { echo "existing $SERVICE_USER has unexpected home: $home" >&2; exit 9; }
    case "$shell" in /usr/sbin/nologin|/sbin/nologin) ;; *) echo "existing $SERVICE_USER has interactive shell: $shell" >&2; exit 10 ;; esac
fi

(
    cd "$MCP_ROOT"
    "$NODE_BIN" -e "Promise.all([import('@modelcontextprotocol/server'), import('@modelcontextprotocol/server/stdio'), import('zod/v4')])" >/dev/null 2>&1
) || { echo "business159-live-shell Node dependencies are not installed for $NODE_BIN" >&2; exit 11; }

for sibling in edge1-secure-mcp-tunnel.service edge1-operator-mcp.service bigbird-ai-tunnel.service; do
    printf '%s active=' "$sibling"
    systemctl is-active "$sibling" 2>/dev/null || true
    printf '%s enabled=' "$sibling"
    systemctl is-enabled "$sibling" 2>/dev/null || true
done

case "$MODE" in
    "") echo "Business159 tunnel dry run passed. No files changed and no service was started/enabled."; exit 0 ;;
    --apply) ;;
    *) echo "unknown argument: $MODE" >&2; exit 12 ;;
esac

systemctl is-enabled --quiet "$SERVICE" 2>/dev/null && { echo "refusing: Business159 tunnel service is enabled; use maintenance workflow" >&2; exit 13; }
systemctl is-active --quiet "$SERVICE" 2>/dev/null && { echo "refusing: Business159 tunnel service is active; use maintenance workflow" >&2; exit 14; }

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home-dir "$STATE_DIR" --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi
install -d -o root -g "$SERVICE_USER" -m 0750 "$ETC_DIR" "$SSH_DIR"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 "$STATE_DIR"
install -d -o root -g root -m 0755 "$LIBEXEC_DIR"
install -o root -g "$SERVICE_USER" -m 0640 "$ROOT/deploy/business159-tunnel/tunnel-client.yaml" "$ETC_DIR/tunnel-client.yaml"
install -o root -g root -m 0755 "$ROOT/deploy/business159-tunnel/business159-secure-mcp-tunnel.sh" "$LIBEXEC_DIR/business159-secure-mcp-tunnel.sh"
install -o root -g root -m 0755 "$ROOT/deploy/business159-tunnel/business159-live-shell.sh" "$LIBEXEC_DIR/business159-live-shell.sh"
install -o root -g root -m 0755 "$ROOT/deploy/business159-tunnel/ssh" "$LIBEXEC_DIR/ssh"
install -o root -g root -m 0644 "$ROOT/deploy/business159-tunnel/business159-secure-mcp-tunnel.service" "$UNIT"
systemctl daemon-reload
systemd-analyze verify "$UNIT"

for f in "$ETC_DIR/runtime-api-key" "$ETC_DIR/tunnel-id" "$SSH_DIR/ssh_config" "$SSH_DIR/known_hosts"; do
    [ ! -e "$f" ] || {
        owner=$(stat -c '%U:%G' "$f"); mode=$(stat -c '%a' "$f")
        [ "$owner" = root:$SERVICE_USER ] && [ "$mode" = 640 ] || { echo "existing $(basename "$f") has unexpected owner/mode: $owner $mode" >&2; exit 15; }
    }
done

if systemctl is-enabled --quiet "$SERVICE" 2>/dev/null || systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
    echo "refusing: staging must not activate or enable Business159 tunnel" >&2; exit 16
fi

echo "Business159 Secure MCP Tunnel assets staged; service remains disabled/inactive."
echo "Provision tunnel-id/runtime-api-key and reviewed SSH config/known_hosts privately, then run validator."
