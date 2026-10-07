#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
units=(edge1-automation-watchdog.service edge1-automation-watchdog.timer edge1-action-lifecycle.service edge1-action-lifecycle.timer edge1-evidence-integrity.service edge1-evidence-integrity.timer edge1-api-surface-health.service edge1-api-surface-health.timer)
verify=(); for u in "${units[@]}"; do verify+=("$ROOT/deploy/automation-wave6/$u"); done
systemd-analyze verify "${verify[@]}"
for d in automation-watchdog action-lifecycle evidence-integrity api-surface-health; do install -d -m 0755 "/var/www/edge1-status/$d"; done
install -d -m 0700 /var/lib/edge1-action-lifecycle /var/lib/edge1-api-surface-health
for u in "${units[@]}"; do install -m 0644 "$ROOT/deploy/automation-wave6/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now edge1-automation-watchdog.timer edge1-action-lifecycle.timer edge1-evidence-integrity.timer edge1-api-surface-health.timer
systemctl start edge1-automation-watchdog.service edge1-action-lifecycle.service edge1-evidence-integrity.service edge1-api-surface-health.service
systemctl start edge1-outstanding-actions.service || true
echo 'Automation wave 6 installed.'
