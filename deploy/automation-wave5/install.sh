#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
units=(edge1-accounting-intake.service edge1-accounting-intake.timer edge1-mail-learning.service edge1-mail-learning.timer edge1-credential-lifecycle.service edge1-credential-lifecycle.timer edge1-ava-quality-control.service edge1-ava-quality-control.timer)
verify=(); for u in "${units[@]}"; do verify+=("$ROOT/deploy/automation-wave5/$u"); done
systemd-analyze verify "${verify[@]}"
for d in accounting-intake mail-learning credential-lifecycle ava-quality; do install -d -m 0755 "/var/www/edge1-status/$d"; done
install -d -m 0700 /var/lib/edge1-accounting-intake
for u in "${units[@]}"; do install -m 0644 "$ROOT/deploy/automation-wave5/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now edge1-accounting-intake.timer edge1-mail-learning.timer edge1-credential-lifecycle.timer edge1-ava-quality-control.timer
systemctl start edge1-accounting-intake.service edge1-mail-learning.service edge1-credential-lifecycle.service edge1-ava-quality-control.service
systemctl start edge1-outstanding-actions.service || true
echo 'Automation wave 5 installed.'
