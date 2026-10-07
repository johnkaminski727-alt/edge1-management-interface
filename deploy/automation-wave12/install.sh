#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
test -s "$ROOT/tools/automation/recovery_rehearsal_bot.py"
systemd-analyze verify "$ROOT/deploy/automation-wave12/edge1-recovery-rehearsal.service" "$ROOT/deploy/automation-wave12/edge1-recovery-rehearsal.timer"
install -d -m 0700 /var/lib/edge1-recovery-rehearsal
install -d -m 0755 /var/www/edge1-status/recovery-rehearsal
install -m 0644 "$ROOT/deploy/automation-wave12/edge1-recovery-rehearsal.service" /etc/systemd/system/edge1-recovery-rehearsal.service
install -m 0644 "$ROOT/deploy/automation-wave12/edge1-recovery-rehearsal.timer" /etc/systemd/system/edge1-recovery-rehearsal.timer
systemctl daemon-reload
systemctl enable --now edge1-recovery-rehearsal.timer
systemctl start edge1-recovery-rehearsal.service
echo 'Automation wave 12 recovery rehearsal installed.'
