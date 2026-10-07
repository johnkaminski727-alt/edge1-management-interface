#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
units=(edge1-git-hygiene.service edge1-git-hygiene.timer edge1-certificate-expiry.service edge1-certificate-expiry.timer edge1-storage-health.service edge1-storage-health.timer edge1-weekly-executive-briefing.service edge1-weekly-executive-briefing.timer)
verify=(); for u in "${units[@]}"; do verify+=("$ROOT/deploy/automation-wave2/$u"); done
systemd-analyze verify "${verify[@]}"
for d in git-hygiene certificate-expiry storage-health executive-briefing; do install -d -m 0755 "/var/www/edge1-status/$d"; done
install -d -m 0700 /var/lib/edge1-git-hygiene
for u in "${units[@]}"; do install -m 0644 "$ROOT/deploy/automation-wave2/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now edge1-git-hygiene.timer edge1-certificate-expiry.timer edge1-storage-health.timer edge1-weekly-executive-briefing.timer
systemctl start edge1-git-hygiene.service edge1-certificate-expiry.service edge1-storage-health.service edge1-weekly-executive-briefing.service
echo 'Automation wave 2 installed.'
