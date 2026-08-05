#!/bin/sh
set -eu

REPO=${EDGE1_SECURITY_AUTH_ROOT:-/opt/edge1-management-interface}
GATEWAY_CONFIG=${EDGE1_SECURITY_AUTH_CONFIG:-/etc/wwcx-edge1-ops/security-auth-gateway.json}
HTTP_CONFIG=${EDGE1_SECURITY_AUTH_HTTP_CONFIG:-/etc/wwcx-edge1-ops/security-auth-http.json}
JWKS=${EDGE1_SECURITY_AUTH_JWKS:-/etc/wwcx-edge1-ops/business159-jwks.json}
SECRET=${EDGE1_OPS_SECRET_FILE:-/etc/edge1-operations-api.secret}

printf 'timestamp=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'host=%s\n' "$(hostname)"
printf 'user=%s\n' "$(id -un)"
printf 'uid=%s\n' "$(id -u)"
printf 'repo=%s\n' "$REPO"

for path in "$REPO" "$GATEWAY_CONFIG" "$HTTP_CONFIG" "$JWKS" "$SECRET"; do
  if [ -e "$path" ]; then
    ls -ld "$path"
  else
    printf 'missing=%s\n' "$path"
  fi
done

if command -v git >/dev/null 2>&1 && [ -d "$REPO/.git" ]; then
  git -C "$REPO" status --short --branch
  git -C "$REPO" rev-parse HEAD
fi

if command -v systemctl >/dev/null 2>&1; then
  for unit in edge1-operations-api.service edge1-security-auth.service apache2.service httpd.service; do
    systemctl show "$unit" --property=LoadState,ActiveState,SubState --no-pager 2>/dev/null || true
  done
fi

if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep -E '(:8097|:8108)([[:space:]]|$)' || true
fi

if command -v curl >/dev/null 2>&1; then
  curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8097/healthz || true
  printf '\n'
fi
