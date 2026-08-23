#!/bin/sh
set -eu
umask 077

APPLY=0
REPO=/opt/edge1-management-interface
SERVICE=edge1-agent-shell-secure-mcp-tunnel.service
ETC_DIR=/etc/edge1-agent-shell-tunnel
CONFIG="$ETC_DIR/tunnel-client.yaml"
TUNNEL_ID_FILE="$ETC_DIR/tunnel-id"
UNIT="/etc/systemd/system/$SERVICE"
SOURCE_DIR=
SOURCE_CONFIG=
SOURCE_UNIT=
LAUNCHER=/usr/local/libexec/edge1-tunnel/edge1-secure-mcp-tunnel.sh
API_KEY_FILE=/etc/edge1-tunnel/runtime-api-key
TOKEN_FILE=/etc/edge1-operator/mcp-token

usage() {
  echo "usage: $0 [--repo PATH] [--apply]" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || { usage; exit 2; }
      REPO=$2
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

SOURCE_DIR="$REPO/deploy/edge1-agent-shell-tunnel"
SOURCE_CONFIG="$SOURCE_DIR/tunnel-client.yaml"
SOURCE_UNIT="$SOURCE_DIR/edge1-agent-shell-secure-mcp-tunnel.service"

[ "$(id -u)" -eq 0 ] || { echo "installer must run as root" >&2; exit 1; }
id edge1-operator >/dev/null 2>&1 || { echo "edge1-operator account missing" >&2; exit 1; }
[ -x /usr/local/bin/tunnel-client ] || { echo "tunnel-client unavailable" >&2; exit 1; }
[ -x "$LAUNCHER" ] || { echo "shared Edge1 tunnel launcher unavailable" >&2; exit 1; }
[ -r "$API_KEY_FILE" ] || { echo "existing Edge1 tunnel runtime API key unavailable" >&2; exit 1; }
[ -r "$TOKEN_FILE" ] || { echo "existing Edge1 MCP bearer token unavailable" >&2; exit 1; }
[ -f "$SOURCE_CONFIG" ] || { echo "source tunnel config missing" >&2; exit 1; }
[ -f "$SOURCE_UNIT" ] || { echo "source systemd unit missing" >&2; exit 1; }

# The ChatGPT workspace tunnel enrollment is a human/account boundary.  This
# installer deliberately never creates, prints, copies, or commits the tunnel
# identifier.  An already-enrolled /etc/.../tunnel-id must exist before apply.
if [ -r "$TUNNEL_ID_FILE" ]; then
  TUNNEL_ID=$(tr -d '\r\n' < "$TUNNEL_ID_FILE")
  case "$TUNNEL_ID" in tunnel_????????????????????????????????) ;; *) echo "existing Agent Shell tunnel id has invalid format" >&2; exit 1 ;; esac
  unset TUNNEL_ID
else
  echo "Agent Shell tunnel enrollment file is missing: $TUNNEL_ID_FILE" >&2
  echo "Create it only from the workspace-enrolled Secure MCP Tunnel ID, then rerun." >&2
  exit 1
fi

python3 - "$SOURCE_CONFIG" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
required = (
    "- channel: main\n      url: http://127.0.0.1:8114/mcp",
    "Authorization: env:EDGE1_MCP_AUTHORIZATION",
    "api_key: file:/etc/edge1-tunnel/runtime-api-key",
    "url_file: /run/edge1-agent-shell-secure-mcp-tunnel/health-url",
    "pid_file: /run/edge1-agent-shell-secure-mcp-tunnel/tunnel-client.pid",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing dedicated Agent Shell tunnel token: {token}")
if "127.0.0.1:8102" in text:
    raise SystemExit("dedicated Agent Shell tunnel must not route the read-only Operator")
PY

printf 'service=%s\n' "$SERVICE"
printf 'endpoint=%s\n' 'http://127.0.0.1:8114/mcp'
printf 'config=%s\n' "$CONFIG"
printf 'tunnel_id_file=%s\n' "$TUNNEL_ID_FILE"
printf 'apply=%s\n' "$APPLY"

if [ "$APPLY" -ne 1 ]; then
  echo "dry-run only; pass --apply to install/update"
  exit 0
fi

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="/var/backups/wwcx-edge1-agent-shell-tunnel-$STAMP"
mkdir -p "$BACKUP"
chmod 700 "$BACKUP"

if [ -f "$CONFIG" ]; then cp -a "$CONFIG" "$BACKUP/tunnel-client.yaml"; else : > "$BACKUP/config-was-absent"; fi
if [ -f "$UNIT" ]; then cp -a "$UNIT" "$BACKUP/$SERVICE"; else : > "$BACKUP/unit-was-absent"; fi

install -d -o root -g edge1-operator -m 0750 "$ETC_DIR"
install -o root -g edge1-operator -m 0640 "$SOURCE_CONFIG" "$CONFIG"
install -o root -g root -m 0644 "$SOURCE_UNIT" "$UNIT"

rollback() {
  echo "Agent Shell tunnel postflight failed; restoring previous files" >&2
  if [ -f "$BACKUP/tunnel-client.yaml" ]; then cp -a "$BACKUP/tunnel-client.yaml" "$CONFIG"; fi
  if [ -f "$BACKUP/$SERVICE" ]; then cp -a "$BACKUP/$SERVICE" "$UNIT"; fi
  systemctl daemon-reload || true
  systemctl restart "$SERVICE" >/dev/null 2>&1 || true
}
trap rollback HUP INT TERM

systemctl daemon-reload
systemd-analyze verify "$UNIT"
systemctl enable --now "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" || { rollback; trap - HUP INT TERM; exit 1; }

HEALTH=$(curl -fsS --max-time 2 http://127.0.0.1:8114/healthz 2>/dev/null || true)
case "$HEALTH" in
  *'"status":"ok"'*'"mode":"full"'*) ;;
  *) rollback; trap - HUP INT TERM; echo "Agent Shell full-mode health failed" >&2; exit 1 ;;
esac

LISTEN=$(ss -lnt 2>/dev/null | awk '$4 == "127.0.0.1:8114" {print $4}')
[ "$LISTEN" = "127.0.0.1:8114" ] || { rollback; trap - HUP INT TERM; echo "Agent Shell listener is not loopback-only" >&2; exit 1; }

# The ordinary read-only Operator/tunnel must remain independently healthy.
systemctl is-active --quiet edge1-secure-mcp-tunnel.service || { rollback; trap - HUP INT TERM; echo "read-only Edge1 tunnel is not active" >&2; exit 1; }
systemctl is-active --quiet edge1-operator-mcp.service || { rollback; trap - HUP INT TERM; echo "read-only Edge1 Operator is not active" >&2; exit 1; }

cat > "$BACKUP/rollback.sh" <<ROLLBACK
#!/bin/sh
set -eu
if [ -f '$BACKUP/tunnel-client.yaml' ]; then cp -a '$BACKUP/tunnel-client.yaml' '$CONFIG'; fi
if [ -f '$BACKUP/$SERVICE' ]; then cp -a '$BACKUP/$SERVICE' '$UNIT'; fi
systemctl daemon-reload
systemctl restart '$SERVICE'
ROLLBACK
chmod 700 "$BACKUP/rollback.sh"

trap - HUP INT TERM
printf 'backup=%s\n' "$BACKUP"
printf 'service_state=%s\n' "$(systemctl is-active "$SERVICE")"
printf 'health=%s\n' "$HEALTH"
printf 'listener=%s\n' "$LISTEN"
