#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
DB=/var/lib/edge1-navigation/navigation.sqlite3
BOOTSTRAP="$ROOT/config/edge1_operator/navigation_registry.json"
SITE=/etc/nginx/sites-enabled/edge1-private.conf

install -d -m 0755 /usr/local/lib/edge1-navigation
install -m 0644 "$ROOT/server/edge1_navigation_registry.py" /usr/local/lib/edge1-navigation/edge1_navigation_registry.py
install -m 0644 "$ROOT/server/edge1_navigation_admin.py" /usr/local/lib/edge1-navigation/edge1_navigation_admin.py
install -m 0644 "$ROOT/server/edge1_navigation_admin_http.py" /usr/local/lib/edge1-navigation/edge1_navigation_admin_http.py
: > /usr/local/lib/edge1-navigation/__init__.py
chmod 0644 /usr/local/lib/edge1-navigation/__init__.py
ln -sfn /usr/local/lib/edge1-navigation /usr/local/lib/edge1_navigation
install -m 0755 "$ROOT/deploy/edge1-navigation/edge1-navigation-db" /usr/local/sbin/edge1-navigation-db
install -m 0755 "$ROOT/deploy/edge1-navigation/edge1-navigation-admin-http" /usr/local/sbin/edge1-navigation-admin-http

install -d -o wwadmin -g wwadmin -m 0750 /var/lib/edge1-navigation
if ! test -s "$DB"; then
  install -o wwadmin -g wwadmin -m 0640 "$BOOTSTRAP" /var/lib/edge1-navigation/bootstrap.json
  sudo -u wwadmin /usr/local/sbin/edge1-navigation-db init --bootstrap /var/lib/edge1-navigation/bootstrap.json --replace
  sudo -u wwadmin /usr/local/sbin/edge1-navigation-db theme mail-room dark
fi
chown wwadmin:wwadmin "$DB"
chmod 0640 "$DB"
touch /var/lib/edge1-navigation/refresh.trigger
chown wwadmin:wwadmin /var/lib/edge1-navigation/refresh.trigger
chmod 0640 /var/lib/edge1-navigation/refresh.trigger

install -d -m 0755 /var/www/edge1-status/navigation-management
install -m 0644 "$ROOT/src/web/navigation-management/index.html" /var/www/edge1-status/navigation-management/index.html
install -m 0644 "$ROOT/src/web/navigation-management/styles.css" /var/www/edge1-status/navigation-management/styles.css
install -m 0644 "$ROOT/src/web/navigation-management/app.js" /var/www/edge1-status/navigation-management/app.js

install -m 0644 "$ROOT/deploy/systemd/edge1-navigation-export.service" /etc/systemd/system/edge1-navigation-export.service
install -m 0644 "$ROOT/deploy/systemd/edge1-navigation-export.path" /etc/systemd/system/edge1-navigation-export.path
install -m 0644 "$ROOT/deploy/systemd/edge1-navigation-export.timer" /etc/systemd/system/edge1-navigation-export.timer
install -m 0644 "$ROOT/deploy/systemd/edge1-navigation-admin.service" /etc/systemd/system/edge1-navigation-admin.service

# Add the API location exactly once before the generic /edge1-ops/ proxy.
python3 - "$SITE" "$ROOT/deploy/nginx/edge1-navigation-admin.location.conf" <<'PY'
from pathlib import Path
import sys
site=Path(sys.argv[1]); snippet=Path(sys.argv[2]).read_text()
s=site.read_text()
if 'location ^~ /edge1-ops/navigation-admin/api/' not in s:
    marker='    location /edge1-ops/ {\n'
    if marker not in s: raise SystemExit('generic /edge1-ops/ nginx location not found')
    s=s.replace(marker,snippet+'\n'+marker,1)
    site.write_text(s)
PY

nginx -t
systemctl daemon-reload
systemctl enable --now edge1-navigation-export.path edge1-navigation-export.timer edge1-navigation-admin.service

/usr/bin/python3 - <<'PY'
import sys
sys.path.insert(0,'/usr/local/lib')
from edge1_navigation.edge1_navigation_admin import upsert_management_module
upsert_management_module()
PY
systemctl start edge1-navigation-export.service
systemctl reload nginx

echo "Edge1 database-backed navigation and Navigation Management UI commissioned."
