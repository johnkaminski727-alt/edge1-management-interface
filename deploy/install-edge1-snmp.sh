#!/bin/sh
set -eu
ROOT=${EDGE1_ROOT:-/opt/edge1-management-interface}
STATUS_ROOT=/var/www/edge1-status
STATUS_DIR=$STATUS_ROOT/snmp
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/var/lib/wwcx-deployment-evidence/snmp/backups/$STAMP

if [ ! -d "$STATUS_ROOT" ]; then
    printf '%s\n' "Missing Operations Center status root: $STATUS_ROOT" >&2
    exit 1
fi

install -d -m 0700 "$BACKUP"
if [ -f "$STATUS_DIR/operations-snmp.json" ]; then
    cp -a "$STATUS_DIR/operations-snmp.json" "$BACKUP/operations-snmp.json"
fi
install -d -o root -g wwadmin -m 0750 /etc/edge1-snmp /etc/edge1-snmp/profiles
install -d -o wwadmin -g wwadmin -m 0700 /var/lib/edge1-snmp
install -d -o wwadmin -g wwadmin -m 0755 "$STATUS_DIR"
if [ -f /etc/edge1-snmp/config.json ]; then
    cp -a /etc/edge1-snmp/config.json "$BACKUP/config.json"
else
    install -o root -g wwadmin -m 0640 "$ROOT/config/edge1-snmp.json.example" /etc/edge1-snmp/config.json
fi
if [ ! -s /etc/edge1-snmp/api.secret ]; then
    umask 077
    dd if=/dev/urandom bs=48 count=1 2>/dev/null | base64 > /etc/edge1-snmp/api.secret
fi
chown root:wwadmin /etc/edge1-snmp/config.json
chmod 0640 /etc/edge1-snmp/config.json
chown wwadmin:wwadmin /etc/edge1-snmp/api.secret
chmod 0600 /etc/edge1-snmp/api.secret
/usr/bin/python3 "$ROOT/server/edge1_snmp_platform.py" init-db
chown wwadmin:wwadmin /var/lib/edge1-snmp/snmp.sqlite3
chmod 0600 /var/lib/edge1-snmp/snmp.sqlite3
install -m 0644 "$ROOT/deploy/edge1-snmp-ai-identity.service" /etc/systemd/system/edge1-snmp-ai-identity.service
install -m 0644 "$ROOT/deploy/edge1-snmp-api.service" /etc/systemd/system/edge1-snmp-api.service
install -m 0644 "$ROOT/deploy/edge1-snmp-poller.service" /etc/systemd/system/edge1-snmp-poller.service
install -m 0644 "$ROOT/deploy/edge1-snmp-poller.timer" /etc/systemd/system/edge1-snmp-poller.timer
install -m 0644 "$ROOT/deploy/edge1-snmp-actions.service" /etc/systemd/system/edge1-snmp-actions.service
install -m 0644 "$ROOT/deploy/edge1-snmp-actions.timer" /etc/systemd/system/edge1-snmp-actions.timer
systemctl daemon-reload
printf '%s\n' "Staged SNMP services. Validate configuration, credential profiles, AI identity and policy gates before enabling." "Backup: $BACKUP"
