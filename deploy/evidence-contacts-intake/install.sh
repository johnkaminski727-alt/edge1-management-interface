#!/bin/sh
set -eu
[ "${1:-}" = "--apply" ] || { echo 'usage: install.sh --apply' >&2; exit 2; }
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/edge1-evidence-intake/inbox /var/lib/edge1-evidence-intake/staging
install -d -o wwadmin -g wwadmin -m 0755 /var/www/edge1-status/evidence-contact-intake
install -m 0644 deploy/evidence-contacts-intake/edge1-evidence-contacts-intake.service /etc/systemd/system/
install -m 0644 deploy/evidence-contacts-intake/edge1-evidence-contacts-intake.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now edge1-evidence-contacts-intake.timer
