#!/bin/sh
set -eu

SERVICE=business159-secure-mcp-tunnel.service
SERVICE_USER=business159-operator
BINARY=/usr/local/bin/tunnel-client
WRAPPER=/usr/local/libexec/business159-tunnel/business159-secure-mcp-tunnel.sh
MCP_WRAPPER=/usr/local/libexec/business159-tunnel/business159-live-shell.sh
SSH_CONFIG=/etc/business159-operator/ssh_config
KNOWN_HOSTS=/etc/business159-operator/known_hosts
EXPECTED_HOST=business159.web-hosting.com
EXPECTED_PRINCIPAL=wwcxjywl

[ "$(id -u)" -eq 0 ] || { echo "run with sudo/root" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "$SERVICE_USER account missing" >&2; exit 2; }
[ -x "$BINARY" ] && [ -x "$WRAPPER" ] && [ -x "$MCP_WRAPPER" ] || { echo "Business159 tunnel runtime assets missing" >&2; exit 3; }

for f in /etc/business159-tunnel/tunnel-client.yaml /etc/business159-tunnel/tunnel-id /etc/business159-tunnel/runtime-api-key "$SSH_CONFIG" "$KNOWN_HOSTS"; do
    [ -r "$f" ] || { echo "required file unavailable: $f" >&2; exit 4; }
done

for f in /etc/business159-tunnel/tunnel-id /etc/business159-tunnel/runtime-api-key "$SSH_CONFIG" "$KNOWN_HOSTS"; do
    owner=$(stat -c '%U:%G' "$f")
    mode=$(stat -c '%a' "$f")
    [ "$owner" = root:$SERVICE_USER ] && [ "$mode" = 640 ] || { echo "unsafe owner/mode for $f: $owner $mode" >&2; exit 5; }
done

systemd-analyze verify "/etc/systemd/system/$SERVICE"

identity=$(runuser -u "$SERVICE_USER" -- /usr/bin/ssh -F "$SSH_CONFIG" -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS" -o ConnectTimeout=10 business159 'printf "host="; hostname -f 2>/dev/null || hostname; printf "principal="; id -un')
printf '%s\n' "$identity"
printf '%s\n' "$identity" | grep -qx "host=$EXPECTED_HOST"
printf '%s\n' "$identity" | grep -qx "principal=$EXPECTED_PRINCIPAL"

runuser -u "$SERVICE_USER" -- "$WRAPPER" doctor

echo "BUSINESS159_TUNNEL_PREFLIGHT=PASS"
