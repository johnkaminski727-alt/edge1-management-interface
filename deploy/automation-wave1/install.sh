#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
files=(
  tools/automation/automation_common.py
  tools/automation/outstanding_actions_bot.py
  tools/automation/document_filing_bot.py
  tools/automation/drift_monitor_bot.py
  tools/automation/backup_verification_bot.py
)
for f in "${files[@]}"; do test -s "$ROOT/$f" || { echo "missing $f" >&2; exit 1; }; done
units=(
 edge1-outstanding-actions.service edge1-outstanding-actions.timer
 edge1-document-filing.service edge1-document-filing.timer
 edge1-drift-monitor.service edge1-drift-monitor.timer
 edge1-backup-verification.service edge1-backup-verification.timer
 edge1-mail-restore-rehearsal.service edge1-mail-restore-rehearsal.timer
)
verify=(); for u in "${units[@]}"; do verify+=("$ROOT/deploy/automation-wave1/$u"); done
systemd-analyze verify "${verify[@]}"
install -d -m 0755 /var/www/edge1-status/outstanding-actions /var/www/edge1-status/document-filing /var/www/edge1-status/drift-monitor /var/www/edge1-status/backup-verification
install -d -m 0750 /var/lib/edge1-document-filing
for u in "${units[@]}"; do install -m 0644 "$ROOT/deploy/automation-wave1/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable --now edge1-outstanding-actions.timer edge1-document-filing.timer edge1-drift-monitor.timer edge1-backup-verification.timer edge1-mail-restore-rehearsal.timer
systemctl start edge1-outstanding-actions.service
systemctl start edge1-document-filing.service
systemctl start edge1-drift-monitor.service
systemctl start edge1-backup-verification.service
echo 'Automation wave 1 installed. Weekly restore rehearsal scheduled; installer did not force a rehearsal.'
