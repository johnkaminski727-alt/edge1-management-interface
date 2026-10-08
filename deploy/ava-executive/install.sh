#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
SITE=/etc/nginx/sites-enabled/edge1-private.conf
for f in tools/automation/ava_executive_orchestrator.py src/web/edge1-ops/ava/index.html src/web/edge1-ops/ava/app.js src/web/edge1-ops/ava/styles.css deploy/ava-executive/edge1-ava-executive.service deploy/ava-executive/edge1-ava-executive.path deploy/ava-executive/edge1-ava-executive.timer deploy/ava-executive/edge1-ava-office-api.location.conf; do test -s "$ROOT/$f" || { echo "missing $f" >&2; exit 1; }; done
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/wwcx-ava-office-manager /var/lib/wwcx-ava-office-manager/report-inbox
install -d -o wwadmin -g wwadmin -m 0755 /var/www/edge1-status/ava
install -m 0644 "$ROOT/src/web/edge1-ops/ava/index.html" /var/www/edge1-status/ava/index.html
install -m 0644 "$ROOT/src/web/edge1-ops/ava/app.js" /var/www/edge1-status/ava/app.js
install -m 0644 "$ROOT/src/web/edge1-ops/ava/styles.css" /var/www/edge1-status/ava/styles.css
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-executive.service" /etc/systemd/system/edge1-ava-executive.service
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-executive.path" /etc/systemd/system/edge1-ava-executive.path
install -m 0644 "$ROOT/deploy/ava-executive/edge1-ava-executive.timer" /etc/systemd/system/edge1-ava-executive.timer
python3 - "$SITE" "$ROOT/deploy/ava-executive/edge1-ava-office-api.location.conf" <<'PY'
from pathlib import Path
import sys
site=Path(sys.argv[1]); snippet=Path(sys.argv[2]).read_text(); text=site.read_text()
if 'location ^~ /edge1-ops/ava-office/api/' not in text:
    marker='    location /edge1-ops/ {\n'
    if marker not in text: raise SystemExit('generic /edge1-ops/ nginx location not found')
    site.write_text(text.replace(marker,snippet+'\n'+marker,1))
PY
nginx -t
systemctl daemon-reload
systemctl enable --now edge1-ava-executive.path edge1-ava-executive.timer
systemctl start edge1-ava-executive.service
systemctl reload nginx
echo 'AVA Executive orchestration layer installed.'
