#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
systemd-analyze verify "$ROOT/deploy/automation-wave7/edge1-catalog-consistency.service" "$ROOT/deploy/automation-wave7/edge1-catalog-consistency.timer"
install -d -m 0755 /var/www/edge1-status/catalog-consistency
install -m 0644 "$ROOT/deploy/automation-wave7/edge1-catalog-consistency.service" /etc/systemd/system/edge1-catalog-consistency.service
install -m 0644 "$ROOT/deploy/automation-wave7/edge1-catalog-consistency.timer" /etc/systemd/system/edge1-catalog-consistency.timer
systemctl daemon-reload
systemctl enable --now edge1-catalog-consistency.timer
systemctl start edge1-catalog-consistency.service
systemctl start edge1-outstanding-actions.service || true
echo 'Automation wave 7 installed.'
