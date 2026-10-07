#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
systemd-analyze verify "$ROOT/deploy/automation-wave10/edge1-update-readiness.service" "$ROOT/deploy/automation-wave10/edge1-update-readiness.timer"
install -d -m 0755 /var/www/edge1-status/update-readiness
install -m 0644 "$ROOT/deploy/automation-wave10/edge1-update-readiness.service" /etc/systemd/system/edge1-update-readiness.service
install -m 0644 "$ROOT/deploy/automation-wave10/edge1-update-readiness.timer" /etc/systemd/system/edge1-update-readiness.timer
systemctl daemon-reload
systemctl enable --now edge1-update-readiness.timer
systemctl start edge1-update-readiness.service
systemctl start edge1-outstanding-actions.service || true
echo 'Automation wave 10 installed.'
