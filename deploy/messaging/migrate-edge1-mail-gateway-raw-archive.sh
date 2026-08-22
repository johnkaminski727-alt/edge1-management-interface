#!/bin/bash
set -euo pipefail

AUTHORIZATION="WWCX-EDGE1-MAIL-GATEWAY-RAW-ARCHIVE-001"
REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
CONFIG=${CONFIG:-$REPO_ROOT/config/messaging/edge1-mail-gateway-v1.json}
ARCHIVE_TOOL=${ARCHIVE_TOOL:-$REPO_ROOT/tools/messaging/edge1_mail_gateway_archive.py}
ACCEPTANCE=${ACCEPTANCE:-$REPO_ROOT/tools/messaging/edge1_mail_gateway_local_acceptance.py}
POSTFIX_ETC=${POSTFIX_ETC:-/etc/postfix}
BACKUP_ROOT=${BACKUP_ROOT:-/var/backups/wwcx-mail-gateway}
ARCHIVE_ROOT=${ARCHIVE_ROOT:-/var/lib/wwcx-mail-gateway/inbound}
STORE=${STORE:-/var/lib/wwcx-mail-room/correspondence.sqlite3}
SYSTEM_SBIN=${SYSTEM_SBIN:-/usr/sbin}
SYSTEM_BIN=${SYSTEM_BIN:-/usr/bin}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

resolve_command() {
    local name=$1
    shift
    local found
    found=$(command -v "$name" 2>/dev/null || true)
    if [ -n "$found" ]; then
        printf '%s\n' "$found"
        return 0
    fi
    local candidate
    for candidate in "$@"; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

if [ "$#" -ne 3 ] || [ "$1" != "--authorization" ] || [ "$2" != "$AUTHORIZATION" ] || [ "$3" != "--execute" ]; then
    echo "Usage: sudo $0 --authorization $AUTHORIZATION --execute" >&2
    exit 2
fi

[ "${EUID:-$(id -u)}" -eq 0 ] || fail "raw archive migration must run as root"

PYTHON3_BIN=${PYTHON3_BIN:-$(resolve_command python3 "$SYSTEM_BIN/python3" || true)}
POSTCONF_BIN=${POSTCONF_BIN:-$(resolve_command postconf "$SYSTEM_SBIN/postconf" "$SYSTEM_BIN/postconf" || true)}
POSTFIX_BIN=${POSTFIX_BIN:-$(resolve_command postfix "$SYSTEM_SBIN/postfix" "$SYSTEM_BIN/postfix" || true)}
SS_BIN=${SS_BIN:-$(resolve_command ss "$SYSTEM_BIN/ss" "$SYSTEM_SBIN/ss" || true)}
RUNUSER_BIN=${RUNUSER_BIN:-$(resolve_command runuser "$SYSTEM_SBIN/runuser" "$SYSTEM_BIN/runuser" || true)}
SYSTEMCTL_BIN=${SYSTEMCTL_BIN:-$(resolve_command systemctl "$SYSTEM_BIN/systemctl" "$SYSTEM_SBIN/systemctl" || true)}

for pair in \
    "python3:$PYTHON3_BIN" \
    "postconf:$POSTCONF_BIN" \
    "postfix:$POSTFIX_BIN" \
    "ss:$SS_BIN" \
    "runuser:$RUNUSER_BIN" \
    "systemctl:$SYSTEMCTL_BIN"
do
    name=${pair%%:*}
    path=${pair#*:}
    [ -n "$path" ] && [ -x "$path" ] || fail "$name is unavailable"
done

[ -f "$CONFIG" ] || fail "gateway configuration is unavailable"
[ -f "$ARCHIVE_TOOL" ] || fail "raw archive tool is unavailable"
[ -f "$ACCEPTANCE" ] || fail "local acceptance tool is unavailable"
[ -f "$POSTFIX_ETC/main.cf" ] || fail "Postfix main.cf is unavailable"
[ -f "$POSTFIX_ETC/master.cf" ] || fail "Postfix master.cf is unavailable"
[ -f "$STORE" ] && [ ! -L "$STORE" ] || fail "live Mail Room store is unavailable or unsafe"
id wwcx-mail-gateway >/dev/null 2>&1 || fail "wwcx-mail-gateway service account is unavailable"

if [ -d "$REPO_ROOT/.git" ]; then
    branch=$(git -C "$REPO_ROOT" branch --show-current)
    [ "$branch" = "main" ] || fail "repository must be on main"
    [ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository working tree is not clean"
fi

[ "$("$POSTCONF_BIN" -h inet_interfaces)" = "loopback-only" ] \
    || fail "migration requires loopback-only Postfix"
[ "$("$POSTCONF_BIN" -h virtual_transport)" = "wwcxmail:" ] \
    || fail "migration requires the accepted wwcxmail transport"
[ "$("$POSTCONF_BIN" -h wwcxmail_destination_recipient_limit)" = "1" ] \
    || fail "migration requires one-recipient wwcxmail delivery"
[ "$("$POSTCONF_BIN" -h virtual_mailbox_domains)" = "hash:/etc/postfix/wwcx-edge1-managed-domains" ] \
    || fail "managed-domain map does not match accepted local gateway state"
[ "$("$POSTCONF_BIN" -h virtual_mailbox_maps)" = "regexp:/etc/postfix/wwcx-edge1-recipient-regexp" ] \
    || fail "recipient map does not match accepted local gateway state"

current_master=$("$POSTCONF_BIN" -M wwcxmail/unix 2>/dev/null || true)
[ -n "$current_master" ] || fail "wwcxmail master service is unavailable"
printf '%s\n' "$current_master" | grep -F 'edge1_mail_gateway_ingest.py' >/dev/null \
    || fail "wwcxmail is not the expected direct-ingest transport"
printf '%s\n' "$current_master" | grep -F -- '--recipient ${original_recipient}' >/dev/null \
    || fail "wwcxmail does not preserve original recipient"
printf '%s\n' "$current_master" | grep -F 'flags=ROq' >/dev/null \
    || fail "wwcxmail does not preserve X-Original-To evidence"

listeners=$( ("$SS_BIN" -lntp 2>/dev/null || "$SS_BIN" -lnt) | awk '$4 ~ /(^|:|\])25$/ {print}' )
if [ -n "$listeners" ] && printf '%s\n' "$listeners" | grep -Ev '127\.0\.0\.1:25|\[::1\]:25|::1:25' | grep . >/dev/null 2>&1; then
    fail "TCP/25 is exposed outside loopback"
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="$BACKUP_ROOT/raw-archive-migration-$stamp"
install -d -o root -g root -m 0700 "$backup"
cp -a "$POSTFIX_ETC/main.cf" "$backup/main.cf.before"
cp -a "$POSTFIX_ETC/master.cf" "$backup/master.cf.before"
"$POSTCONF_BIN" -n > "$backup/postconf-n.before.txt"
"$POSTCONF_BIN" -M > "$backup/postconf-M.before.txt"
printf '%s\n' "$listeners" > "$backup/port25.before.txt"
printf '%s\n' "$current_master" > "$backup/wwcxmail.before.txt"

rollback_armed=1
rollback() {
    local status=$?
    trap - ERR INT TERM
    if [ "${rollback_armed:-0}" -eq 1 ]; then
        echo "Migration failed; restoring Postfix configuration from $backup" >&2
        cp -a "$backup/main.cf.before" "$POSTFIX_ETC/main.cf"
        cp -a "$backup/master.cf.before" "$POSTFIX_ETC/master.cf"
        "$POSTFIX_BIN" check >/dev/null 2>&1 || true
        "$POSTFIX_BIN" reload >/dev/null 2>&1 || true
        echo "rollback_performed=true" > "$backup/rollback.txt"
    fi
    exit "$status"
}
trap rollback ERR INT TERM

install -d -o wwcx-mail-gateway -g wwcx-mail-gateway -m 0700 "$ARCHIVE_ROOT"
"$POSTCONF_BIN" -e 'message_size_limit=52428800'
MASTER_VALUE='wwcxmail/unix=wwcxmail unix - n n - - pipe flags=ROq user=wwcx-mail-gateway argv=/usr/bin/python3 /opt/edge1-management-interface/tools/messaging/edge1_mail_gateway_archive.py --stdin --recipient ${original_recipient} --queue-id ${queue_id} --archive-root /var/lib/wwcx-mail-gateway/inbound --store /var/lib/wwcx-mail-room/correspondence.sqlite3'
"$POSTCONF_BIN" -M -e "$MASTER_VALUE"

"$POSTFIX_BIN" check
"$POSTFIX_BIN" reload
sleep 1
"$SYSTEMCTL_BIN" is-active --quiet postfix || fail "Postfix is not active after migration reload"

listeners_after=$( ("$SS_BIN" -lntp 2>/dev/null || "$SS_BIN" -lnt) | awk '$4 ~ /(^|:|\])25$/ {print}' )
if [ -n "$listeners_after" ] && printf '%s\n' "$listeners_after" | grep -Ev '127\.0\.0\.1:25|\[::1\]:25|::1:25' | grep . >/dev/null 2>&1; then
    fail "Postfix exposed TCP/25 outside loopback after migration"
fi
[ "$("$POSTCONF_BIN" -h inet_interfaces)" = "loopback-only" ] \
    || fail "Postfix did not remain loopback-only"
[ "$("$POSTCONF_BIN" -h message_size_limit)" = "52428800" ] \
    || fail "raw archive message-size boundary is not active"
new_master=$("$POSTCONF_BIN" -M wwcxmail/unix)
printf '%s\n' "$new_master" | grep -F 'edge1_mail_gateway_archive.py' >/dev/null \
    || fail "wwcxmail did not switch to raw archive transport"
printf '%s\n' "$new_master" | grep -F 'edge1_mail_gateway_ingest.py' >/dev/null \
    && fail "direct-ingest transport remains active"

"$RUNUSER_BIN" -u wwcx-mail-gateway -- \
    "$PYTHON3_BIN" "$ACCEPTANCE" \
    --config "$CONFIG" \
    --store "$STORE" \
    --archive-root "$ARCHIVE_ROOT" \
    --domain creekco.ca \
    --execute > "$backup/local-acceptance.json"

"$POSTCONF_BIN" -n > "$backup/postconf-n.after.txt"
"$POSTCONF_BIN" -M > "$backup/postconf-M.after.txt"
printf '%s\n' "$listeners_after" > "$backup/port25.after.txt"
printf '%s\n' "$new_master" > "$backup/wwcxmail.after.txt"
echo "rollback_performed=false" > "$backup/rollback.txt"
{
    cd "$backup"
    find . -type f ! -name sha256.txt -print | LC_ALL=C sort | while IFS= read -r file; do
        sha256sum "$file"
    done
} > "$backup/sha256.txt"

rollback_armed=0
trap - ERR INT TERM
cat "$backup/local-acceptance.json"
echo
echo "Edge1 Mail Gateway raw archive migration accepted."
echo "Backup/evidence directory: $backup"
echo "TCP/25 remains loopback-only."
echo "No DNS, MX, firewall, certificate, provider, or outbound-delivery change was made."
