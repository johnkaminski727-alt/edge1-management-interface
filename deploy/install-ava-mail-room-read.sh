#!/bin/sh
set -eu

REPO=/opt/edge1-management-interface
MAIL_SERVICE=wwcx-mail-room.service
WORKER_SERVICE=private-ai-browser-worker.service
ENV_FILE=/etc/wwcx/ava-mail-read.env
MAIL_DROPIN=/etc/systemd/system/wwcx-mail-room.service.d/97-ava-mail-read.conf
WORKER_DROPIN=/etc/systemd/system/private-ai-browser-worker.service.d/97-ava-mail-read.conf
RELEASE_ROOT=/opt/wwcx-email/releases
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NEW_RELEASE="$RELEASE_ROOT/ava-mail-read-$STAMP"
BACKUP=/var/backups/ava-mail-read-$STAMP

die(){ echo "ERROR: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run as root"
[ -f "$REPO/server/mail_room_http.py" ] || die "Mail Room source missing"
[ -f "$REPO/server/private_ai_browser_worker.py" ] || die "Ava worker source missing"
[ -f "$REPO/server/ava_agent_controller.py" ] || die "Ava controller source missing"

CURRENT=$(systemctl show "$MAIL_SERVICE" -p WorkingDirectory --value)
[ -n "$CURRENT" ] && [ -d "$CURRENT" ] || die "current Mail Room release unavailable"
[ -f "$CURRENT/server/mail_room_http.py" ] || die "current Mail Room release invalid"

install -d -o root -g root -m 0700 "$BACKUP"
[ -f "$MAIL_DROPIN" ] && cp -a "$MAIL_DROPIN" "$BACKUP/mail-room-dropin.conf" || true
[ -f "$WORKER_DROPIN" ] && cp -a "$WORKER_DROPIN" "$BACKUP/worker-dropin.conf" || true
[ -f "$ENV_FILE" ] && cp -a "$ENV_FILE" "$BACKUP/ava-mail-read.env" || true
printf '%s\n' "$CURRENT" > "$BACKUP/previous-release.txt"

if [ ! -f "$ENV_FILE" ]; then
  umask 077
  python3 - <<'PY' > "$ENV_FILE"
import secrets
print('WWCX_AVA_MAIL_READ_KEY=' + secrets.token_urlsafe(48))
PY
  chown root:root "$ENV_FILE"
  chmod 0600 "$ENV_FILE"
fi
[ "$(grep -c '^WWCX_AVA_MAIL_READ_KEY=' "$ENV_FILE")" -eq 1 ] || die "read token file invalid"

cp -a "$CURRENT" "$NEW_RELEASE"
install -o root -g root -m 0644 "$REPO/server/mail_room_http.py" "$NEW_RELEASE/server/mail_room_http.py"
python3 -m py_compile "$NEW_RELEASE/server/mail_room_http.py" "$REPO/server/private_ai_browser_worker.py" "$REPO/server/ava_agent_controller.py"

install -d -o root -g root -m 0755 "$(dirname "$MAIL_DROPIN")" "$(dirname "$WORKER_DROPIN")"
cat > "$MAIL_DROPIN" <<EOF
[Service]
WorkingDirectory=$NEW_RELEASE
ExecStart=
ExecStart=/usr/bin/python3 -B -m server.mail_room_http --database /var/lib/wwcx-mail-room-drafts/drafts.sqlite3
EnvironmentFile=$ENV_FILE
EOF
cat > "$WORKER_DROPIN" <<EOF
[Service]
EnvironmentFile=$ENV_FILE
EOF
chmod 0644 "$MAIL_DROPIN" "$WORKER_DROPIN"

systemctl daemon-reload
systemctl restart "$MAIL_SERVICE" "$WORKER_SERVICE"
systemctl is-active --quiet "$MAIL_SERVICE" || die "Mail Room failed to start"
systemctl is-active --quiet "$WORKER_SERVICE" || die "Ava browser worker failed to start"

python3 - <<'PY'
import json, urllib.request
key=''
for line in open('/etc/wwcx/ava-mail-read.env'):
    if line.startswith('WWCX_AVA_MAIL_READ_KEY='):
        key=line.rstrip('\n').split('=',1)[1]
assert len(key) >= 32
req=urllib.request.Request(
    'http://127.0.0.1:8117/edge1-ops/mail-room/api/ava/messages?folder=inbox',
    headers={'X-Ava-Mail-Read-Key':key},
)
with urllib.request.urlopen(req,timeout=10) as r:
    data=json.load(r)
assert data.get('contract') == 'wwcx.ava-mail-room-read.v1'
assert data.get('send_authorized') is False
assert data.get('mutation_authorized') is False
assert isinstance(data.get('messages'),list)
print('Ava Mail Room read acceptance: PASS')
print('messages_visible=' + str(len(data['messages'])))
print('body_policy=' + str(data.get('body_policy')))
PY

echo "Installed Ava Mail Room read connector."
echo "release=$NEW_RELEASE"
echo "backup=$BACKUP"
echo "No mailbox mutation or send capability was enabled."
