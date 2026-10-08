#!/bin/sh
set -eu
[ "${1:-}" = "--apply" ] || { echo 'usage: install.sh --apply' >&2; exit 2; }
ROOT=/opt/edge1-management-interface
SITE=/etc/nginx/sites-enabled/edge1-private.conf
DEST=/var/www/edge1-status
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/edge1-evidence-intake/provider-bridge
install -d -m 0755 "$DEST/library-sources"
install -m 0644 "$ROOT/src/web/library-sources/index.html" "$DEST/library-sources/index.html"
install -m 0644 "$ROOT/src/web/library-sources/styles.css" "$DEST/library-sources/styles.css"
install -m 0644 "$ROOT/src/web/library-sources/app.js" "$DEST/library-sources/app.js"
install -m 0644 "$ROOT/deploy/library-sources-admin/edge1-library-sources-admin.service" /etc/systemd/system/
install -m 0644 "$ROOT/deploy/library-sources-admin/edge1-library-provider-poll.service" /etc/systemd/system/
install -m 0644 "$ROOT/deploy/library-sources-admin/edge1-library-provider-poll.timer" /etc/systemd/system/
python3 - "$SITE" "$ROOT/deploy/library-sources-admin/edge1-library-sources-admin.location.conf" <<'PY'
from pathlib import Path
import sys
site=Path(sys.argv[1]); snippet=Path(sys.argv[2]).read_text(); s=site.read_text()
if 'location ^~ /edge1-ops/library-sources/api/' not in s:
    marker='    location /edge1-ops/ {\n'
    if marker not in s: raise SystemExit('generic /edge1-ops/ nginx location not found')
    s=s.replace(marker,snippet+'\n'+marker,1); site.write_text(s)
PY
nginx -t
systemctl daemon-reload
systemctl enable --now edge1-library-sources-admin.service edge1-library-provider-poll.timer
# Add/update one navigation record without replacing customized navigation order.
python3 - <<'PY'
import sqlite3
p='/var/lib/edge1-navigation/navigation.sqlite3'; c=sqlite3.connect(p)
r=('library-sources','Library & Sources','Intelligence',6,'/edge1-ops/status/library-sources/','/edge1-ops/status/library-sources/','/edge1-ops/status/library-sources/','accepted_live','authenticated_admin','Unified Private Library source catalog, connector/bridge state, evidence indexing and accounting intake.',1,1,'live_catalog_and_provider_sync','primary',1,1,'link','inherit')
c.execute('''INSERT INTO navigation_modules(id,label,section,sort_order,browser_route,candidate_route,runtime_route,availability,authorization,description,palette,toolbox,evidence_status,menu_visibility,dashboard_visibility,enabled,icon,theme,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
ON CONFLICT(id) DO UPDATE SET label=excluded.label,section=excluded.section,sort_order=excluded.sort_order,browser_route=excluded.browser_route,candidate_route=excluded.candidate_route,runtime_route=excluded.runtime_route,availability=excluded.availability,authorization=excluded.authorization,description=excluded.description,palette=excluded.palette,toolbox=excluded.toolbox,evidence_status=excluded.evidence_status,menu_visibility=excluded.menu_visibility,dashboard_visibility=excluded.dashboard_visibility,enabled=excluded.enabled,icon=excluded.icon,theme=excluded.theme,updated_at=CURRENT_TIMESTAMP''',r)
c.commit(); c.close()
PY
touch /var/lib/edge1-navigation/refresh.trigger
systemctl start edge1-navigation-export.service
systemctl reload nginx
echo 'Library Sources admin/UI installed.'
