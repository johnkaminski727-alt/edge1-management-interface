#!/bin/sh
set -eu
[ "${1:-}" = "--apply" ] || { echo 'usage: install.sh --apply' >&2; exit 2; }
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/bigbird-ai-library/catalog
install -d -o wwadmin -g wwadmin -m 0755 /var/www/edge1-status/library-source-catalog /var/www/edge1-status/library-accounting /var/www/edge1-status/library-external-index
install -m 0644 deploy/library-source-catalog/edge1-library-source-catalog.service /etc/systemd/system/
install -m 0644 deploy/library-source-catalog/edge1-library-source-catalog.timer /etc/systemd/system/
install -m 0644 deploy/library-source-catalog/edge1-library-external-index.service /etc/systemd/system/
install -m 0644 deploy/library-source-catalog/edge1-library-external-index.timer /etc/systemd/system/
install -m 0644 deploy/library-source-catalog/edge1-library-accounting-extract.service /etc/systemd/system/
install -m 0644 deploy/library-source-catalog/edge1-library-accounting-extract.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now edge1-library-source-catalog.timer edge1-library-external-index.timer edge1-library-accounting-extract.timer
systemctl start edge1-library-source-catalog.service edge1-library-external-index.service edge1-library-accounting-extract.service
