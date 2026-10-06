#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
SITE=/etc/nginx/sites-enabled/edge1-private.conf
install -d -m 0755 /usr/local/lib/edge1-egress
install -m 0644 "$ROOT/server/egress/"*.py /usr/local/lib/edge1-egress/
: > /usr/local/lib/edge1-egress/__init__.py
chmod 0644 /usr/local/lib/edge1-egress/__init__.py
ln -sfn /usr/local/lib/edge1-egress /usr/local/lib/edge1_egress
install -m 0755 "$ROOT/deploy/edge1-egress/edge1-egress-reconcile" /usr/local/sbin/edge1-egress-reconcile
install -m 0755 "$ROOT/deploy/edge1-egress/edge1-egress-collector" /usr/local/sbin/edge1-egress-collector
install -m 0755 "$ROOT/deploy/edge1-egress/edge1-egress-admin-http" /usr/local/sbin/edge1-egress-admin-http
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/edge1-egress
touch /var/lib/edge1-egress/reconcile.trigger
chown wwadmin:wwadmin /var/lib/edge1-egress/reconcile.trigger
chmod 0640 /var/lib/edge1-egress/reconcile.trigger
python3 - <<'PY'
import sys,os
sys.path.insert(0,'/usr/local/lib')
from edge1_egress.edge1_egress_registry import init_db
init_db()
os.chown('/var/lib/edge1-egress/egress.sqlite3',__import__('pwd').getpwnam('wwadmin').pw_uid,__import__('grp').getgrnam('wwadmin').gr_gid)
os.chmod('/var/lib/edge1-egress/egress.sqlite3',0o640)
PY
install -d -m 0755 /var/www/edge1-status/egress-routing
install -m 0644 "$ROOT/src/web/egress-routing/index.html" /var/www/edge1-status/egress-routing/index.html
install -m 0644 "$ROOT/src/web/egress-routing/styles.css" /var/www/edge1-status/egress-routing/styles.css
install -m 0644 "$ROOT/src/web/egress-routing/app.js" /var/www/edge1-status/egress-routing/app.js
for u in edge1-egress-reconcile.service edge1-egress-reconcile.path edge1-egress-reconcile.timer edge1-egress-collector.service edge1-egress-admin.service; do install -m 0644 "$ROOT/deploy/systemd/$u" "/etc/systemd/system/$u"; done
python3 - "$SITE" "$ROOT/deploy/nginx/edge1-egress-admin.location.conf" <<'PY'
from pathlib import Path
import sys
site=Path(sys.argv[1]);snippet=Path(sys.argv[2]).read_text();s=site.read_text()
if 'location ^~ /edge1-ops/egress-admin/api/' not in s:
 marker='    location /edge1-ops/ {\n'
 if marker not in s:raise SystemExit('generic edge1 ops location missing')
 s=s.replace(marker,snippet+'\n'+marker,1);site.write_text(s)
PY
nginx -t
systemctl daemon-reload
# Add navigation row without changing authorization semantics.
python3 - <<'PY'
import sqlite3
p='/var/lib/edge1-navigation/navigation.sqlite3';c=sqlite3.connect(p)
r=('egress-routing','Egress Routing','Network',43,'/edge1-ops/status/egress-routing/','/edge1-ops/status/egress-routing/','/edge1-ops/status/egress-routing/','accepted_live','authenticated_admin','Automatic service-aware country egress routing and gateway health.',1,1,'database_backed_live_policy','primary',1,1,'inherit')
c.execute('''insert into navigation_modules(id,label,section,sort_order,browser_route,candidate_route,runtime_route,availability,authorization,description,palette,toolbox,evidence_status,menu_visibility,dashboard_visibility,enabled,theme,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) on conflict(id) do update set label=excluded.label,section=excluded.section,sort_order=excluded.sort_order,browser_route=excluded.browser_route,candidate_route=excluded.candidate_route,runtime_route=excluded.runtime_route,availability=excluded.availability,authorization=excluded.authorization,description=excluded.description,palette=excluded.palette,toolbox=excluded.toolbox,evidence_status=excluded.evidence_status,menu_visibility=excluded.menu_visibility,dashboard_visibility=excluded.dashboard_visibility,enabled=excluded.enabled,theme=excluded.theme,updated_at=CURRENT_TIMESTAMP''',r);c.commit()
PY
touch /var/lib/edge1-navigation/refresh.trigger
systemctl start edge1-navigation-export.service
systemctl reload nginx
systemctl enable --now edge1-egress-admin.service
systemctl start edge1-egress-reconcile.service
systemctl enable --now edge1-egress-collector.service
systemctl enable --now edge1-egress-reconcile.path edge1-egress-reconcile.timer
echo 'Edge1 selective egress routing, collector, authenticated UI and reconciliation commissioned.'
