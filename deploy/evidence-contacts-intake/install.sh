#!/bin/sh
set -eu
[ "${1:-}" = "--apply" ] || { echo 'usage: install.sh --apply' >&2; exit 2; }
install -d -o wwadmin -g wwadmin -m 0750 /var/lib/edge1-evidence-intake/inbox /var/lib/edge1-evidence-intake/staging
install -d -o wwadmin -g wwadmin -m 0755 /var/www/edge1-status/evidence-contact-intake
VENV=/opt/edge1-management-interface/.venv-evidence-extractor
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --disable-pip-version-check 'pypdf==5.9.0'
chown -R wwadmin:wwadmin "$VENV"
find "$VENV" -type d -exec chmod u+rwx,go+rx {} +
find "$VENV" -type f -exec chmod u+rw,go+r {} +
chmod 0755 "$VENV/bin/python" "$VENV/bin/pip"
install -m 0644 deploy/evidence-contacts-intake/edge1-evidence-contacts-intake.service /etc/systemd/system/
install -m 0644 deploy/evidence-contacts-intake/edge1-evidence-contacts-intake.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now edge1-evidence-contacts-intake.timer
