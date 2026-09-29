#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-}"
SOURCE_ROOT="${EDGE1_RELEASE_ROOT:-/opt/edge1-management-interface}"
CONF="/etc/nginx/sites-available/edge1-private.conf"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/edge1-contacts-ava-ingress-${STAMP}"
CONTACTS_DEST="/var/www/contacts"
AVA_DEST="/var/www/ava-office"

case "$MODE" in
  "") echo "Use --apply to publish and stage authenticated Contacts/Ava routes."; exit 0 ;;
  --apply) ;;
  *) echo "Usage: $0 [--apply]" >&2; exit 2 ;;
esac

test "$(id -u)" -eq 0 || { echo "STOP: --apply requires root" >&2; exit 1; }
test -f "$CONF" || { echo "STOP: missing $CONF" >&2; exit 1; }
test -f "$SOURCE_ROOT/src/web/contacts/index.html" || { echo "STOP: Contacts source missing" >&2; exit 1; }
test -f "$SOURCE_ROOT/src/web/contacts/app.js" || { echo "STOP: Contacts app source missing" >&2; exit 1; }
test -f "$SOURCE_ROOT/src/web/contacts/styles.css" || { echo "STOP: Contacts styles source missing" >&2; exit 1; }
test -f "$SOURCE_ROOT/src/web/ava-office/index.html" || { echo "STOP: Ava source missing" >&2; exit 1; }
test -f "$SOURCE_ROOT/src/web/ava-office/app.js" || { echo "STOP: Ava app source missing" >&2; exit 1; }
test -f "$SOURCE_ROOT/src/web/ava-office/styles.css" || { echo "STOP: Ava styles source missing" >&2; exit 1; }

grep -q 'location = /_edge1_status_session_check' "$CONF" || {
  echo "STOP: authenticated status session-check route from Phase 3I is not installed" >&2
  exit 1
}
grep -q 'location @edge1_status_login' "$CONF" || {
  echo "STOP: authenticated login handoff from Phase 3I is not installed" >&2
  exit 1
}

curl -fsS --max-time 3 http://127.0.0.1:8098/ >/dev/null || {
  echo "STOP: Edge1 private web gateway on 8098 is unavailable" >&2
  exit 1
}
curl -fsS --max-time 3 http://127.0.0.1:8116/healthz >/dev/null || {
  echo "STOP: Ava Office read API on 8116 is unavailable" >&2
  exit 1
}

mkdir -p "$BACKUP"
chmod 0700 "$BACKUP"
cp -a "$CONF" "$BACKUP/edge1-private.conf.before"

CONTACTS_EXISTED=0
AVA_EXISTED=0
if [ -e "$CONTACTS_DEST" ]; then
  CONTACTS_EXISTED=1
  cp -a "$CONTACTS_DEST" "$BACKUP/contacts.before"
fi
if [ -e "$AVA_DEST" ]; then
  AVA_EXISTED=1
  cp -a "$AVA_DEST" "$BACKUP/ava-office.before"
fi

rollback() {
  rc=$?
  trap - EXIT INT TERM
  cp -a "$BACKUP/edge1-private.conf.before" "$CONF" || true

  rm -rf "$CONTACTS_DEST"
  if [ "$CONTACTS_EXISTED" -eq 1 ]; then
    cp -a "$BACKUP/contacts.before" "$CONTACTS_DEST"
  fi

  rm -rf "$AVA_DEST"
  if [ "$AVA_EXISTED" -eq 1 ]; then
    cp -a "$BACKUP/ava-office.before" "$AVA_DEST"
  fi

  nginx -t >/dev/null 2>&1 && systemctl reload nginx.service || true
  echo "Rolled back authenticated Contacts/Ava ingress." >&2
  exit "$rc"
}
trap rollback EXIT INT TERM

install -d -m 0755 "$CONTACTS_DEST" "$AVA_DEST"
install -m 0644 "$SOURCE_ROOT/src/web/contacts/index.html" "$CONTACTS_DEST/index.html"
install -m 0644 "$SOURCE_ROOT/src/web/contacts/app.js" "$CONTACTS_DEST/app.js"
install -m 0644 "$SOURCE_ROOT/src/web/contacts/styles.css" "$CONTACTS_DEST/styles.css"
install -m 0644 "$SOURCE_ROOT/src/web/ava-office/index.html" "$AVA_DEST/index.html"
install -m 0644 "$SOURCE_ROOT/src/web/ava-office/app.js" "$AVA_DEST/app.js"
install -m 0644 "$SOURCE_ROOT/src/web/ava-office/styles.css" "$AVA_DEST/styles.css"

python3 - "$CONF" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = "    location /edge1-ops/ {"
block = r'''
    # Authenticated Contacts & Relationship Management candidate.
    location ^~ /edge1-ops/contacts-api/ {
        auth_request /_edge1_status_session_check;
        error_page 401 = @edge1_status_login;
        limit_except GET { deny all; }

        proxy_pass http://127.0.0.1:8098/api/contacts/;
        proxy_set_header Host edge1.ww.cx;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Cookie $http_cookie;
        add_header Cache-Control "no-store";
    }

    location ^~ /edge1-ops/contacts/ {
        auth_request /_edge1_status_session_check;
        error_page 401 = @edge1_status_login;
        limit_except GET { deny all; }

        proxy_pass http://127.0.0.1:8098/contacts/;
        proxy_set_header Host edge1.ww.cx;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Cookie $http_cookie;
        add_header Cache-Control "no-store";
    }

    # Authenticated Ava Office candidate. Browser access is read-only;
    # operator action/shell gates remain independent and unchanged.
    location ^~ /edge1-ops/ava-api/ {
        auth_request /_edge1_status_session_check;
        error_page 401 = @edge1_status_login;
        limit_except GET { deny all; }

        proxy_pass http://127.0.0.1:8116/api/ava-office/;
        proxy_set_header Host edge1.ww.cx;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Cookie $http_cookie;
        add_header Cache-Control "no-store";
    }

    location ^~ /edge1-ops/ava/ {
        auth_request /_edge1_status_session_check;
        error_page 401 = @edge1_status_login;
        limit_except GET { deny all; }

        proxy_pass http://127.0.0.1:8098/ava-office/;
        proxy_set_header Host edge1.ww.cx;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Cookie $http_cookie;
        add_header Cache-Control "no-store";
    }

'''

if "location ^~ /edge1-ops/contacts/" in text or "location ^~ /edge1-ops/ava/" in text:
    print("PASS: Contacts/Ava authenticated routes already present")
elif marker not in text:
    raise SystemExit("STOP: expected /edge1-ops/ nginx location was not found")
else:
    path.write_text(text.replace(marker, block + marker, 1))
    print("PASS: Contacts/Ava authenticated routes staged")
PY

nginx -t
systemctl reload nginx.service
test "$(systemctl is-active nginx.service)" = active

cmp -s "$SOURCE_ROOT/src/web/contacts/index.html" "$CONTACTS_DEST/index.html"
cmp -s "$SOURCE_ROOT/src/web/contacts/app.js" "$CONTACTS_DEST/app.js"
cmp -s "$SOURCE_ROOT/src/web/contacts/styles.css" "$CONTACTS_DEST/styles.css"
cmp -s "$SOURCE_ROOT/src/web/ava-office/index.html" "$AVA_DEST/index.html"
cmp -s "$SOURCE_ROOT/src/web/ava-office/app.js" "$AVA_DEST/app.js"
cmp -s "$SOURCE_ROOT/src/web/ava-office/styles.css" "$AVA_DEST/styles.css"

cat >"$BACKUP/rollback.sh" <<ROLLBACK
#!/usr/bin/env bash
set -Eeuo pipefail
cp -a "$BACKUP/edge1-private.conf.before" "$CONF"
rm -rf "$CONTACTS_DEST"
if [ "$CONTACTS_EXISTED" -eq 1 ]; then cp -a "$BACKUP/contacts.before" "$CONTACTS_DEST"; fi
rm -rf "$AVA_DEST"
if [ "$AVA_EXISTED" -eq 1 ]; then cp -a "$BACKUP/ava-office.before" "$AVA_DEST"; fi
nginx -t
systemctl reload nginx.service
echo "Restored previous Contacts/Ava browser state."
ROLLBACK
chmod 0700 "$BACKUP/rollback.sh"

trap - EXIT INT TERM

echo "PASS: Contacts and Ava authenticated candidate ingress installed."
echo "Browser candidates:"
echo "  /edge1-ops/contacts/"
echo "  /edge1-ops/ava/"
echo "Rollback: $BACKUP/rollback.sh"
