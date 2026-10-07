#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
units=(edge1-website-health.service edge1-website-health.timer edge1-seo-audit.service edge1-seo-audit.timer)
verify=(); for u in "${units[@]}"; do verify+=("$ROOT/deploy/automation-wave4/$u"); done
systemd-analyze verify "${verify[@]}"
install -d -m 0755 /var/www/edge1-status/website-health /var/www/edge1-status/seo-audit
for u in "${units[@]}"; do install -m 0644 "$ROOT/deploy/automation-wave4/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now edge1-website-health.timer edge1-seo-audit.timer
systemctl start edge1-website-health.service
systemctl start edge1-seo-audit.service
echo 'Automation wave 4 installed.'
