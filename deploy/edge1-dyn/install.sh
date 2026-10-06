#!/bin/bash
set -euo pipefail
[ "${1:-}" = "--apply" ] || { echo "usage: $0 --apply" >&2; exit 2; }
install -d -o root -g root -m 0700 /var/lib/edge1-dyn
install -m 0644 deploy/edge1-dyn/edge1-dyn-dns-admin.service /etc/systemd/system/edge1-dyn-dns-admin.service
install -m 0644 deploy/nginx/edge1-dyn-dns-admin.location.conf /etc/nginx/snippets/edge1-dyn-dns-admin.conf
python3 - <<'PY2'
from pathlib import Path
p=Path('/etc/nginx/sites-available/edge1-private.conf')
s=p.read_text(); inc='    include /etc/nginx/snippets/edge1-dyn-dns-admin.conf;\n'
if inc not in s:
    marker='    location /edge1-ops/ {\n'
    if marker not in s: raise SystemExit('private nginx insertion marker missing')
    s=s.replace(marker,inc+'\n'+marker,1); p.write_text(s)
PY2
nginx -t
systemctl reload nginx
systemctl daemon-reload
systemctl enable --now edge1-dyn-dns-admin.service
