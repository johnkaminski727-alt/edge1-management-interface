#!/bin/sh
set -eu
ROOT=/opt/edge1-management-interface
install -d -m 0750 -o wwadmin -g wwadmin /var/lib/edge1-contacts-maintenance
install -d -m 0700 -o root -g root /var/lib/wwcx-mail-intelligence /var/lib/wwcx-mail-intelligence/attachments
install -d -m 0750 -o root -g bigbird-ai /var/lib/wwcx-daily-briefings
for unit in edge1-mail-contact-intake.service edge1-mail-contact-intake.timer edge1-ava-daily-briefing.service edge1-ava-daily-briefing.timer; do
  install -m 0644 "$ROOT/deploy/mail-intelligence/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now edge1-mail-contact-intake.timer edge1-ava-daily-briefing.timer
systemctl start edge1-mail-contact-intake.service
printf 'Mail intelligence automation installed.\n'
