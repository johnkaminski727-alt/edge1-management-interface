#!/bin/sh
set -eu

SERVICE=edge1-operator-mcp.service

printf 'Checking service: %s\n' "$SERVICE"
systemctl is-enabled "$SERVICE" 2>/dev/null || true
systemctl is-active "$SERVICE" 2>/dev/null || true

printf '\nListening ports:\n'
ss -lnt 2>/dev/null | head -20 || true

printf '\nOperator directories:\n'
for path in /var/lib/edge1-operator /opt/edge1-management-interface; do
  if [ -e "$path" ]; then
    printf 'present: %s\n' "$path"
  else
    printf 'missing: %s\n' "$path"
  fi
done
