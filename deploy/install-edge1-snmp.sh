#!/bin/sh
set -eu
ROOT=${EDGE1_ROOT:-/opt/edge1-management-interface}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/var/lib/wwcx-deployment-evidence/snmp/backups/$STAMP
install -d -m 0700 "$BACKUP" /etc/edge1-snmp/profiles /var/lib/edge1-snmp
if [ -f /etc/edge1-snmp/config.json ]; then cp -a /etc/edge1-snmp/config.json "$BACKUP/config.json"; else install -m 0600 "$ROOT/config/edge1-snmp.json.example" /etc/edge1-snmp/config.json; fi
if [ ! -s /etc/edge1-snmp/api.secret ]; then umask 077; dd if=/dev/urandom bs=48 count=1 2>/dev/null | base64 > /etc/edge1-snmp/api.secret; fi
chmod 0600 /etc/edge1-snmp/api.secret /etc/edge1-snmp/config.json
/usr/bin/python3 "$ROOT/server/edge1_snmp_platform.py" init-db
install -m 0644 "$ROOT/deploy/edge1-snmp-api.service" /etc/systemd/system/edge1-snmp-api.service
install -m 0644 "$ROOT/deploy/edge1-snmp-poller.service" /etc/systemd/system/edge1-snmp-poller.service
install -m 0644 "$ROOT/deploy/edge1-snmp-poller.timer" /etc/systemd/system/edge1-snmp-poller.timer
install -m 0644 "$ROOT/deploy/edge1-snmp-actions.service" /etc/systemd/system/edge1-snmp-actions.service
install -m 0644 "$ROOT/deploy/edge1-snmp-actions.timer" /etc/systemd/system/edge1-snmp-actions.timer
systemctl daemon-reload
printf '%s\n' "Staged SNMP services. Validate configuration, credential profiles, AI identity and policy gates before enabling." "Backup: $BACKUP"
