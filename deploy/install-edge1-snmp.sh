#!/bin/sh
set -eu
ROOT=${EDGE1_ROOT:-/opt/edge1-management-interface}
STATUS_ROOT=/var/www/edge1-status
STATUS_DIR=$STATUS_ROOT/snmp
LIBEXEC_DIR=/usr/local/libexec/edge1-snmp
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
if [ -d "$LIBEXEC_DIR" ]; then
    install -d -m 0700 "$BACKUP/libexec"
    cp -a "$LIBEXEC_DIR/." "$BACKUP/libexec/"
fi
install -d -m 0700 "$BACKUP/systemd"
for unit in \
    edge1-snmp-ai-identity.service \
    edge1-snmp-api.service \
    edge1-snmp-poller.service \
    edge1-snmp-poller.timer \
    edge1-snmp-actions.service \
    edge1-snmp-actions.timer
do
    if [ -f "/etc/systemd/system/$unit" ]; then
        cp -a "/etc/systemd/system/$unit" "$BACKUP/systemd/$unit"
    fi
done

install -d -o root -g wwadmin -m 0750 /etc/edge1-snmp /etc/edge1-snmp/profiles
install -d -o wwadmin -g wwadmin -m 0700 /var/lib/edge1-snmp
install -d -o wwadmin -g wwadmin -m 0700 /var/lib/edge1-snmp/server-pollers
install -d -o wwadmin -g wwadmin -m 0755 "$STATUS_DIR"
install -d -o root -g root -m 0755 "$LIBEXEC_DIR"

# Install a root-owned runtime snapshot so SNMP services never execute code from
# the shared live Git checkout used by unrelated Edge1 services.
for source in "$ROOT"/server/edge1_snmp_*.py "$ROOT/server/operations_snmp_exporter.py"; do
    [ -f "$source" ] || {
        printf '%s\n' "Missing SNMP runtime source: $source" >&2
        exit 1
    }
    install -o root -g root -m 0644 "$source" "$LIBEXEC_DIR/$(basename "$source")"
done
install -o root -g root -m 0755 "$ROOT/deploy/prepare-edge1-snmp-ai-credentials.sh" "$LIBEXEC_DIR/prepare-edge1-snmp-ai-credentials.sh"

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
EDGE1_SNMP_DB=/var/lib/edge1-snmp/snmp.sqlite3 \
EDGE1_SNMP_CONFIG=/etc/edge1-snmp/config.json \
EDGE1_SNMP_PROFILE_DIR=/etc/edge1-snmp/profiles \
/usr/bin/python3 "$LIBEXEC_DIR/edge1_snmp_platform.py" init-db
EDGE1_SNMP_DB=/var/lib/edge1-snmp/snmp.sqlite3 \
/usr/bin/python3 "$LIBEXEC_DIR/edge1_snmp_server_pollers.py" list >/dev/null
chown wwadmin:wwadmin /var/lib/edge1-snmp/snmp.sqlite3
chmod 0600 /var/lib/edge1-snmp/snmp.sqlite3
install -m 0644 "$ROOT/deploy/edge1-snmp-ai-identity.service" /etc/systemd/system/edge1-snmp-ai-identity.service
install -m 0644 "$ROOT/deploy/edge1-snmp-api.service" /etc/systemd/system/edge1-snmp-api.service
install -m 0644 "$ROOT/deploy/edge1-snmp-poller.service" /etc/systemd/system/edge1-snmp-poller.service
install -m 0644 "$ROOT/deploy/edge1-snmp-poller.timer" /etc/systemd/system/edge1-snmp-poller.timer
install -m 0644 "$ROOT/deploy/edge1-snmp-actions.service" /etc/systemd/system/edge1-snmp-actions.service
install -m 0644 "$ROOT/deploy/edge1-snmp-actions.timer" /etc/systemd/system/edge1-snmp-actions.timer
systemctl daemon-reload
printf '%s\n' "Staged SNMP services from root-owned runtime snapshot. Validate configuration, credential profiles, AI identity and policy gates before enabling." "Runtime: $LIBEXEC_DIR" "Backup: $BACKUP"
