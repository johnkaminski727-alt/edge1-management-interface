#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
systemd-analyze verify "$ROOT/deploy/automation-wave9/edge1-domain-renewal.service" "$ROOT/deploy/automation-wave9/edge1-domain-renewal.timer"
install -d -m 0755 /var/www/edge1-status/domain-renewal
install -m 0644 "$ROOT/deploy/automation-wave9/edge1-domain-renewal.service" /etc/systemd/system/edge1-domain-renewal.service
install -m 0644 "$ROOT/deploy/automation-wave9/edge1-domain-renewal.timer" /etc/systemd/system/edge1-domain-renewal.timer
systemctl daemon-reload
systemctl enable --now edge1-domain-renewal.timer
systemctl start edge1-domain-renewal.service
systemctl start edge1-outstanding-actions.service || true
echo 'Automation wave 9 installed.'
