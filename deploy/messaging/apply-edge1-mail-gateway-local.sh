#!/bin/bash
set -euo pipefail

AUTHORIZATION="WWCX-EDGE1-MAIL-GATEWAY-LOCAL-APPLY-001"
REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
CONFIG=${CONFIG:-$REPO_ROOT/config/messaging/edge1-mail-gateway-v1.json}
RENDERER=${RENDERER:-$REPO_ROOT/tools/messaging/render_edge1_mail_gateway_postfix.py}
ACCEPTANCE=${ACCEPTANCE:-$REPO_ROOT/tools/messaging/edge1_mail_gateway_local_acceptance.py}
POSTFIX_ETC=${POSTFIX_ETC:-/etc/postfix}
BACKUP_ROOT=${BACKUP_ROOT:-/var/backups/wwcx-mail-gateway}
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

[ "${EUID:-$(id -u)}" -eq 0 ] || fail "local apply must run as root"

PYTHON3_BIN=${PYTHON3_BIN:-$(resolve_command python3 "$SYSTEM_BIN/python3" || true)}
POSTCONF_BIN=${POSTCONF_BIN:-$(resolve_command postconf "$SYSTEM_SBIN/postconf" "$SYSTEM_BIN/postconf" || true)}
POSTMAP_BIN=${POSTMAP_BIN:-$(resolve_command postmap "$SYSTEM_SBIN/postmap" "$SYSTEM_BIN/postmap" || true)}
POSTFIX_BIN=${POSTFIX_BIN:-$(resolve_command postfix "$SYSTEM_SBIN/postfix" "$SYSTEM_BIN/postfix" || true)}
SS_BIN=${SS_BIN:-$(resolve_command ss "$SYSTEM_BIN/ss" "$SYSTEM_SBIN/ss" || true)}
RUNUSER_BIN=${RUNUSER_BIN:-$(resolve_command runuser "$SYSTEM_SBIN/runuser" "$SYSTEM_BIN/runuser" || true)}

for pair in \
    "python3:$PYTHON3_BIN" \
    "postconf:$POSTCONF_BIN" \
    "postmap:$POSTMAP_BIN" \
    "postfix:$POSTFIX_BIN" \
    "ss:$SS_BIN" \
    "runuser:$RUNUSER_BIN"
do
    name=${pair%%:*}
    path=${pair#*:}
    [ -n "$path" ] && [ -x "$path" ] || fail "$name is unavailable"
done

[ -f "$CONFIG" ] || fail "gateway configuration is unavailable"
[ -f "$RENDERER" ] || fail "gateway renderer is unavailable"
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

work=$(mktemp -d /tmp/wwcx-edge1-mail-gateway-apply.XXXXXX)
cleanup() {
    rm -rf "$work"
}
trap cleanup EXIT

"$PYTHON3_BIN" "$RENDERER" --config "$CONFIG" --output-dir "$work/rendered" >/dev/null

grep -Fx 'inet_interfaces = loopback-only' "$work/rendered/main.cf.fragment" >/dev/null \
    || fail "rendered configuration is not loopback-only"
grep -Fx 'relay_domains =' "$work/rendered/main.cf.fragment" >/dev/null \
    || fail "rendered configuration does not clear relay domains"
grep -Fx 'wwcxmail_destination_recipient_limit = 1' "$work/rendered/main.cf.fragment" >/dev/null \
    || fail "rendered configuration lacks single-recipient delivery"
grep -F -- '--recipient ${original_recipient}' "$work/rendered/master.cf.fragment" >/dev/null \
    || fail "rendered pipe does not preserve original recipient"
grep -F 'flags=ROq' "$work/rendered/master.cf.fragment" >/dev/null \
    || fail "rendered pipe does not add X-Original-To evidence"
if grep -q '^ww\.cx ' "$work/rendered/wwcx-edge1-managed-domains"; then
    fail "ww.cx unexpectedly appears in managed domains"
fi

listeners=$(("$SS_BIN" -lntp 2>/dev/null || "$SS_BIN" -lnt) | awk '$4 ~ /(^|:|\])25$/ {print}')
if [ -n "$listeners" ] && printf '%s\n' "$listeners" | grep -Ev '127\.0\.0\.1:25|\[::1\]:25|::1:25' | grep . >/dev/null 2>&1; then
    fail "TCP/25 is already exposed outside loopback"
fi

current_domains=$("$POSTCONF_BIN" -h virtual_mailbox_domains 2>/dev/null || true)
current_maps=$("$POSTCONF_BIN" -h virtual_mailbox_maps 2>/dev/null || true)
current_transport=$("$POSTCONF_BIN" -h virtual_transport 2>/dev/null || true)
current_wwcxmail=$("$POSTCONF_BIN" -M wwcxmail/unix 2>/dev/null || true)

[ -z "$current_wwcxmail" ] || fail "wwcxmail master.cf service already exists; inspect before reapplying"
if [ -n "$current_domains" ] && [ "$current_domains" != '$virtual_mailbox_maps' ]; then
    fail "existing virtual_mailbox_domains is not the known default placeholder"
fi
[ -z "$current_maps" ] || fail "existing virtual_mailbox_maps is active; refusing to overwrite"
if [ -n "$current_transport" ] && [ "$current_transport" != "virtual" ]; then
    fail "existing virtual_transport is not the known default"
fi

for path in \
    "$POSTFIX_ETC/wwcx-edge1-managed-domains" \
    "$POSTFIX_ETC/wwcx-edge1-managed-domains.db" \
    "$POSTFIX_ETC/wwcx-edge1-recipient-regexp"
do
    [ ! -e "$path" ] || fail "managed Postfix path already exists: $path"
done

stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="$BACKUP_ROOT/local-apply-$stamp"
install -d -o root -g root -m 0700 "$backup"
cp -a "$POSTFIX_ETC/main.cf" "$backup/main.cf.before"
cp -a "$POSTFIX_ETC/master.cf" "$backup/master.cf.before"
"$POSTCONF_BIN" -n > "$backup/postconf-n.before.txt"
"$POSTCONF_BIN" -M > "$backup/postconf-M.before.txt"
printf '%s\n' "$listeners" > "$backup/port25.before.txt"
cp -a "$work/rendered" "$backup/rendered"

rollback_armed=1
rollback() {
    local status=$?
    trap - ERR INT TERM
    if [ "${rollback_armed:-0}" -eq 1 ]; then
        echo "Apply failed; restoring Postfix configuration from $backup" >&2
        cp -a "$backup/main.cf.before" "$POSTFIX_ETC/main.cf"
        cp -a "$backup/master.cf.before" "$POSTFIX_ETC/master.cf"
        rm -f \
            "$POSTFIX_ETC/wwcx-edge1-managed-domains" \
            "$POSTFIX_ETC/wwcx-edge1-managed-domains.db" \
            "$POSTFIX_ETC/wwcx-edge1-recipient-regexp"
        "$POSTFIX_BIN" check >/dev/null 2>&1 || true
        "$POSTFIX_BIN" reload >/dev/null 2>&1 || true
        echo "rollback_performed=true" > "$backup/rollback.txt"
    fi
    exit "$status"
}
trap rollback ERR INT TERM

install -o root -g root -m 0644 \
    "$work/rendered/wwcx-edge1-managed-domains" \
    "$POSTFIX_ETC/wwcx-edge1-managed-domains"
install -o root -g root -m 0644 \
    "$work/rendered/wwcx-edge1-recipient-regexp" \
    "$POSTFIX_ETC/wwcx-edge1-recipient-regexp"
"$POSTMAP_BIN" "$POSTFIX_ETC/wwcx-edge1-managed-domains"

"$POSTCONF_BIN" -e 'inet_interfaces=loopback-only'
"$POSTCONF_BIN" -e 'smtpd_recipient_restrictions=permit_mynetworks,reject_unauth_destination'
"$POSTCONF_BIN" -e 'relay_domains='
"$POSTCONF_BIN" -e 'virtual_mailbox_domains=hash:/etc/postfix/wwcx-edge1-managed-domains'
"$POSTCONF_BIN" -e 'virtual_mailbox_maps=regexp:/etc/postfix/wwcx-edge1-recipient-regexp'
"$POSTCONF_BIN" -e 'virtual_transport=wwcxmail:'
"$POSTCONF_BIN" -e 'wwcxmail_destination_recipient_limit=1'

MASTER_VALUE='wwcxmail/unix=wwcxmail unix - n n - - pipe flags=ROq user=wwcx-mail-gateway argv=/usr/bin/python3 /opt/edge1-management-interface/tools/messaging/edge1_mail_gateway_ingest.py --stdin --recipient ${original_recipient} --queue-id ${queue_id} --store /var/lib/wwcx-mail-room/correspondence.sqlite3'
"$POSTCONF_BIN" -M -e "$MASTER_VALUE"

"$POSTFIX_BIN" check
[ "$("$POSTMAP_BIN" -q creekco.ca hash:"$POSTFIX_ETC/wwcx-edge1-managed-domains")" = "OK" ] \
    || fail "managed-domain lookup failed"
[ "$("$POSTMAP_BIN" -q acceptance@creekco.ca regexp:"$POSTFIX_ETC/wwcx-edge1-recipient-regexp")" = "OK" ] \
    || fail "catch-all recipient lookup failed"
[ -z "$("$POSTMAP_BIN" -q acceptance@ww.cx regexp:"$POSTFIX_ETC/wwcx-edge1-recipient-regexp")" ] \
    || fail "ww.cx unexpectedly matches local catch-all map"

"$POSTFIX_BIN" reload
sleep 1
systemctl is-active --quiet postfix || fail "Postfix is not active after reload"

listeners_after=$(("$SS_BIN" -lntp 2>/dev/null || "$SS_BIN" -lnt) | awk '$4 ~ /(^|:|\])25$/ {print}')
if [ -n "$listeners_after" ] && printf '%s\n' "$listeners_after" | grep -Ev '127\.0\.0\.1:25|\[::1\]:25|::1:25' | grep . >/dev/null 2>&1; then
    fail "Postfix exposed TCP/25 outside loopback after reload"
fi
[ "$("$POSTCONF_BIN" -h inet_interfaces)" = "loopback-only" ] \
    || fail "Postfix did not retain loopback-only binding"
[ "$("$POSTCONF_BIN" -h virtual_transport)" = "wwcxmail:" ] \
    || fail "Postfix virtual transport is not wwcxmail"
[ "$("$POSTCONF_BIN" -h wwcxmail_destination_recipient_limit)" = "1" ] \
    || fail "Postfix single-recipient limit is not active"

"$RUNUSER_BIN" -u wwcx-mail-gateway -- \
    "$PYTHON3_BIN" "$ACCEPTANCE" \
    --config "$CONFIG" \
    --store "$STORE" \
    --domain creekco.ca \
    --execute > "$backup/local-acceptance.json"

"$POSTCONF_BIN" -n > "$backup/postconf-n.after.txt"
"$POSTCONF_BIN" -M > "$backup/postconf-M.after.txt"
printf '%s\n' "$listeners_after" > "$backup/port25.after.txt"
{
    cd "$backup"
    find . -type f ! -name sha256.txt -print | LC_ALL=C sort | while IFS= read -r file; do
        sha256sum "$file"
    done
} > "$backup/sha256.txt"

echo "rollback_performed=false" > "$backup/rollback.txt"
rollback_armed=0
trap - ERR INT TERM

cat "$backup/local-acceptance.json"
echo
echo "Edge1 Mail Gateway local-only apply accepted."
echo "Backup/evidence directory: $backup"
echo "TCP/25 remains loopback-only."
echo "No DNS, MX, firewall, certificate, provider, or outbound-delivery change was made."
