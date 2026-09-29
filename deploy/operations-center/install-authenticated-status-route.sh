#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-}"
CONF="/etc/nginx/sites-available/edge1-private.conf"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/edge1-authenticated-status-${STAMP}"

case "$MODE" in
  "") echo "Use --apply to install the authenticated /edge1-ops/status/ route."; exit 0 ;;
  --apply) ;;
  *) echo "Usage: $0 [--apply]" >&2; exit 2 ;;
esac

test "$(id -u)" -eq 0 || { echo "STOP: --apply requires root" >&2; exit 1; }
test -f "$CONF" || { echo "STOP: missing $CONF" >&2; exit 1; }
test -d /var/www/edge1-status || { echo "STOP: /var/www/edge1-status is not deployed" >&2; exit 1; }

nginx -V 2>&1 | grep -q -- '--with-http_auth_request_module' || {
  echo "STOP: nginx http_auth_request_module is unavailable" >&2
  exit 1
}

mkdir -p "$BACKUP"
chmod 0700 "$BACKUP"
cp -a "$CONF" "$BACKUP/edge1-private.conf.before"

python3 - "$CONF" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

marker = "    location /edge1-ops/ {"
block = r'''
    # Authenticated read-only Edge1 module tree.
    # The Edge1 session cookie is scoped to /edge1-ops/, so these
    # specialist pages remain behind the same session boundary.
    location = /_edge1_status_session_check {
        internal;
        proxy_pass http://127.0.0.1:8108/edge1-ops/session;
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
        proxy_set_header Host edge1.ww.cx;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Cookie $http_cookie;
    }

    location @edge1_status_login {
        return 302 https://ww.cx/admin/edge1-security-login.php;
    }

    location ^~ /edge1-ops/status/ {
        auth_request /_edge1_status_session_check;
        error_page 401 = @edge1_status_login;

        alias /var/www/edge1-status/;
        index index.html;

        add_header Cache-Control "no-store";
        add_header X-Content-Type-Options "nosniff";
        add_header Referrer-Policy "no-referrer";
        add_header X-Frame-Options "DENY";
    }

'''

if "location ^~ /edge1-ops/status/" in text:
    print("PASS: authenticated status route already installed")
elif marker not in text:
    raise SystemExit("STOP: expected /edge1-ops/ nginx location was not found")
else:
    path.write_text(text.replace(marker, block + marker, 1))
    print("PASS: authenticated status route staged")
PY

nginx -t
systemctl reload nginx.service
test "$(systemctl is-active nginx.service)" = active

cat >"$BACKUP/rollback.sh" <<ROLLBACK
#!/usr/bin/env bash
set -Eeuo pipefail
cp -a "$BACKUP/edge1-private.conf.before" "$CONF"
nginx -t
systemctl reload nginx.service
echo "Restored previous private nginx configuration."
ROLLBACK
chmod 0700 "$BACKUP/rollback.sh"

echo "PASS: authenticated module ingress installed."
echo "Rollback: $BACKUP/rollback.sh"
