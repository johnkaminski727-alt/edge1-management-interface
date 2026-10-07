#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
systemd-analyze verify "$ROOT/deploy/automation-wave8/edge1-security-baseline.service" "$ROOT/deploy/automation-wave8/edge1-security-baseline.timer"
install -d -m 0755 /var/www/edge1-status/security-baseline
install -m 0644 "$ROOT/deploy/automation-wave8/edge1-security-baseline.service" /etc/systemd/system/edge1-security-baseline.service
install -m 0644 "$ROOT/deploy/automation-wave8/edge1-security-baseline.timer" /etc/systemd/system/edge1-security-baseline.timer
systemctl daemon-reload
systemctl enable --now edge1-security-baseline.timer
systemctl start edge1-security-baseline.service
systemctl start edge1-outstanding-actions.service || true
echo 'Automation wave 8 installed.'
