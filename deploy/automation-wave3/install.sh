#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
units=(edge1-service-self-heal.service edge1-service-self-heal.timer edge1-mail-domain-health.service edge1-mail-domain-health.timer edge1-knowledge-consolidation.service edge1-knowledge-consolidation.timer)
verify=(); for u in "${units[@]}"; do verify+=("$ROOT/deploy/automation-wave3/$u"); done
systemd-analyze verify "${verify[@]}"
for d in service-self-heal mail-domain-health knowledge-consolidation; do install -d -m 0755 "/var/www/edge1-status/$d"; done
install -d -m 0700 /var/lib/edge1-service-self-heal
for u in "${units[@]}"; do install -m 0644 "$ROOT/deploy/automation-wave3/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now edge1-service-self-heal.timer edge1-mail-domain-health.timer edge1-knowledge-consolidation.timer
systemctl start edge1-service-self-heal.service edge1-mail-domain-health.service edge1-knowledge-consolidation.service
echo 'Automation wave 3 installed.'
