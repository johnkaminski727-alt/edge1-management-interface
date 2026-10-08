#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
SITE=/etc/nginx/sites-enabled/edge1-private.conf
for f in tools/automation/ava_executive_orchestrator.py tools/automation/ava_workflow_dispatcher.py tools/automation/ava_operations_intelligence.py server/ava_dispatch_admin.py config/ava-executive-capabilities.json config/ava-workflow-templates.json src/web/edge1-ops/ava/index.html src/web/edge1-ops/ava/app.js src/web/edge1-ops/ava/styles.css deploy/ava-executive/edge1-ava-executive.service deploy/ava-executive/edge1-ava-executive.path deploy/ava-executive/edge1-ava-executive.timer deploy/ava-executive/edge1-ava-dispatch-admin.service deploy/ava-executive/edge1-ava-workflow-dispatcher.service deploy/ava-executive/edge1-ava-workflow-dispatcher.path deploy/ava-executive/edge1-ava-workflow-dispatcher.timer deploy/ava-executive/edge1-ava-operations-intelligence.service deploy/ava-executive/edge1-ava-operations-intelligence.timer deploy/ava-executive/edge1-ava-office-api.location.conf deploy/ava-executive/edge1-ava-delegation-api.location.conf; do test -s "$ROOT/$f" || { echo "missing $f" >&2; exit 1; }; done
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/wwcx-ava-office-manager /var/lib/wwcx-ava-office-manager/report-inbox /var/lib/wwcx-ava-office-manager/workflow-inbox
install -d -o wwadmin -g wwadmin -m 0755 /var/www/edge1-status/ava
install -m 0644 "$ROOT/src/web/edge1-ops/ava/index.html" /var/www/edge1-status/ava/index.html
install -m 0644 "$ROOT/src/web/edge1-ops/ava/app.js" /var/www/edge1-status/ava/app.js
install -m 0644 "$ROOT/src/web/edge1-ops/ava/styles.css" /var/www/edge1-status/ava/styles.css
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-executive.service" /etc/systemd/system/edge1-ava-executive.service
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-executive.path" /etc/systemd/system/edge1-ava-executive.path
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-executive.timer" /etc/systemd/system/edge1-ava-executive.timer
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-dispatch-admin.service" /etc/systemd/system/edge1-ava-dispatch-admin.service
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-workflow-dispatcher.service" /etc/systemd/system/edge1-ava-workflow-dispatcher.service
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-workflow-dispatcher.path" /etc/systemd/system/edge1-ava-workflow-dispatcher.path
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-workflow-dispatcher.timer" /etc/systemd/system/edge1-ava-workflow-dispatcher.timer
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-operations-intelligence.service" /etc/systemd/system/edge1-ava-operations-intelligence.service
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-operations-intelligence.timer" /etc/systemd/system/edge1-ava-operations-intelligence.timer
python3 - "$SITE" "$ROOT/deploy/ava-executive/edge1-ava-office-api.location.conf" "$ROOT/deploy/ava-executive/edge1-ava-delegation-api.location.conf" <<'PY'
from pathlib import Path
import sys
site=Path(sys.argv[1]); office=Path(sys.argv[2]).read_text(); delegation=Path(sys.argv[3]).read_text(); text=site.read_text()
marker='    location /edge1-ops/ {\n'
if marker not in text: raise SystemExit('generic /edge1-ops/ nginx location not found')
changed=False
if 'location ^~ /edge1-ops/ava-office/api/' not in text:
    text=text.replace(marker,office+'\n'+marker,1); changed=True
if 'location = /edge1-ops/ava-dispatch/api/workflows' not in text:
    text=text.replace(marker,delegation+'\n'+marker,1); changed=True
if changed: site.write_text(text)
PY
nginx -t
systemctl daemon-reload
systemctl enable --now edge1-ava-dispatch-admin.service edge1-ava-executive.path edge1-ava-executive.timer edge1-ava-workflow-dispatcher.path edge1-ava-workflow-dispatcher.timer edge1-ava-operations-intelligence.timer
systemctl start edge1-ava-executive.service edge1-ava-workflow-dispatcher.service edge1-ava-operations-intelligence.service
systemctl reload nginx
echo 'AVA Executive orchestration layer installed.'
