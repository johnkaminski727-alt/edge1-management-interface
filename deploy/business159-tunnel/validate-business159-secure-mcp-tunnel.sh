#!/bin/sh
set -eu

SERVICE=business159-secure-mcp-tunnel.service
SERVICE_USER=business159-operator
BINARY=/usr/local/bin/tunnel-client
WRAPPER=/usr/local/libexec/business159-tunnel/business159-secure-mcp-tunnel.sh
MCP_WRAPPER=/usr/local/libexec/business159-tunnel/business159-live-shell.sh
POLICY_HELPER=/usr/local/libexec/business159-tunnel/set-business159-filesystem-smoke-mode.sh
POLICY_FILE=/etc/business159-operator/runtime-policy
SSH_CONFIG=/etc/business159-operator/ssh_config
KNOWN_HOSTS=/etc/business159-operator/known_hosts
EXPECTED_HOST=business159.web-hosting.com
EXPECTED_PRINCIPAL=wwcxjywl

[ "$(id -u)" -eq 0 ] || { echo "run with sudo/root" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "$SERVICE_USER account missing" >&2; exit 2; }
[ -x "$BINARY" ] && [ -x "$WRAPPER" ] && [ -x "$MCP_WRAPPER" ] && [ -x "$POLICY_HELPER" ] || { echo "Business159 tunnel runtime assets missing" >&2; exit 3; }

for f in /etc/business159-tunnel/tunnel-client.yaml /etc/business159-tunnel/tunnel-id /etc/business159-tunnel/runtime-api-key "$SSH_CONFIG" "$KNOWN_HOSTS"; do
    [ -r "$f" ] || { echo "required file unavailable: $f" >&2; exit 4; }
done

for f in /etc/business159-tunnel/tunnel-id /etc/business159-tunnel/runtime-api-key "$SSH_CONFIG" "$KNOWN_HOSTS"; do
    owner=$(stat -c '%U:%G' "$f")
    mode=$(stat -c '%a' "$f")
    [ "$owner" = root:$SERVICE_USER ] && [ "$mode" = 640 ] || { echo "unsafe owner/mode for $f: $owner $mode" >&2; exit 5; }
done

if [ -e "$POLICY_FILE" ]; then
    [ ! -L "$POLICY_FILE" ] && [ -f "$POLICY_FILE" ] || { echo "runtime policy must be a regular non-symlink file: $POLICY_FILE" >&2; exit 6; }
    owner=$(stat -c '%U:%G' "$POLICY_FILE")
    mode=$(stat -c '%a' "$POLICY_FILE")
    [ "$owner" = root:$SERVICE_USER ] && [ "$mode" = 640 ] || { echo "unsafe owner/mode for $POLICY_FILE: $owner $mode" >&2; exit 7; }
    python3 - "$POLICY_FILE" <<'PY'
from pathlib import Path
import sys
entries = {}
for raw in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    line = raw.strip()
    if not line:
        continue
    if '=' not in line:
        raise SystemExit(f'invalid runtime policy line: {line!r}')
    key, value = line.split('=', 1)
    if key in entries:
        raise SystemExit(f'duplicate runtime policy key: {key}')
    entries[key] = value
required = {
    'BUSINESS159_ALLOW_DEPLOY',
    'BUSINESS159_ALLOW_FILESYSTEM',
    'BUSINESS159_ENABLE_RAW_SHELL',
}
if set(entries) != required:
    raise SystemExit('runtime policy must contain exactly the three approved Business159 mutation gates')
if entries['BUSINESS159_ALLOW_DEPLOY'] != '0':
    raise SystemExit('runtime policy may not enable Business159 deployment apply')
if entries['BUSINESS159_ENABLE_RAW_SHELL'] != '0':
    raise SystemExit('runtime policy may not enable Business159 raw shell')
if entries['BUSINESS159_ALLOW_FILESYSTEM'] not in {'0', '1'}:
    raise SystemExit('runtime policy filesystem gate must be 0 or 1')
PY
fi

systemd-analyze verify "/etc/systemd/system/$SERVICE"

identity=$(runuser -u "$SERVICE_USER" -- /usr/bin/ssh -F "$SSH_CONFIG" -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS" -o ConnectTimeout=10 business159 'printf "host="; hostname -f 2>/dev/null || hostname; printf "principal="; id -un')
printf '%s\n' "$identity"
printf '%s\n' "$identity" | grep -qx "host=$EXPECTED_HOST"
printf '%s\n' "$identity" | grep -qx "principal=$EXPECTED_PRINCIPAL"

runuser -u "$SERVICE_USER" -- "$WRAPPER" doctor

echo "BUSINESS159_TUNNEL_PREFLIGHT=PASS"
