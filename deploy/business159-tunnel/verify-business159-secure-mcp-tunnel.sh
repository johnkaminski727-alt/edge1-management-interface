#!/bin/sh
set -eu

SERVICE=business159-secure-mcp-tunnel.service
HEALTH_URL_FILE=/run/business159-secure-mcp-tunnel/health-url

systemctl is-active --quiet "$SERVICE" || { echo "service_active=fail"; exit 2; }
printf 'service_active=active\n'
systemctl is-enabled --quiet "$SERVICE" || { echo "service_enabled=fail"; exit 3; }
printf 'service_enabled=enabled\n'
policy=$(systemctl show "$SERVICE" -p Restart --value)
[ "$policy" = on-failure ] || { echo "restart_policy=$policy"; exit 4; }
printf 'restart_policy=%s\n' "$policy"
[ -r "$HEALTH_URL_FILE" ] || { echo "health_url_file=missing"; exit 5; }
base=$(cat "$HEALTH_URL_FILE")
case "$base" in http://127.0.0.1:*|http://localhost:*) ;; *) echo "health_url=unexpected"; exit 6 ;; esac
/usr/bin/curl -fsS --max-time 5 "$base/readyz" >/dev/null
printf 'readyz=pass\n'

for sibling in edge1-operator-mcp.service bigbird-ai-tunnel.service; do
    printf '%s active=' "$sibling"
    systemctl is-active "$sibling" 2>/dev/null || true
    printf '%s enabled=' "$sibling"
    systemctl is-enabled "$sibling" 2>/dev/null || true
done
