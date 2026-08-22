#!/bin/bash
set -euo pipefail
umask 077

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
CONFIG=${CONFIG:-$REPO_ROOT/config/messaging/edge1-mail-gateway-v1.json}
ARCHIVE_ROOT=${ARCHIVE_ROOT:-/var/lib/wwcx-mail-gateway/inbound}
STORE=${STORE:-/var/lib/wwcx-mail-room/correspondence.sqlite3}
SERVICE_HOSTNAME=${SERVICE_HOSTNAME:-mail.ww.cx}
SYSTEM_SBIN=${SYSTEM_SBIN:-/usr/sbin}
SYSTEM_BIN=${SYSTEM_BIN:-/usr/bin}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

resolve_command() {
    local name=$1
    shift
    local found candidate
    found=$(command -v "$name" 2>/dev/null || true)
    if [ -n "$found" ]; then
        printf '%s\n' "$found"
        return 0
    fi
    for candidate in "$@"; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

[ "${EUID:-$(id -u)}" -eq 0 ] || fail "public-readiness preflight must run with sudo"

PYTHON3_BIN=${PYTHON3_BIN:-$(resolve_command python3 "$SYSTEM_BIN/python3" || true)}
POSTCONF_BIN=${POSTCONF_BIN:-$(resolve_command postconf "$SYSTEM_SBIN/postconf" "$SYSTEM_BIN/postconf" || true)}
SS_BIN=${SS_BIN:-$(resolve_command ss "$SYSTEM_BIN/ss" "$SYSTEM_SBIN/ss" || true)}
IP_BIN=${IP_BIN:-$(resolve_command ip "$SYSTEM_SBIN/ip" "$SYSTEM_BIN/ip" || true)}
GETENT_BIN=${GETENT_BIN:-$(resolve_command getent "$SYSTEM_BIN/getent" "$SYSTEM_SBIN/getent" || true)}
STAT_BIN=${STAT_BIN:-$(resolve_command stat "$SYSTEM_BIN/stat" || true)}
DF_BIN=${DF_BIN:-$(resolve_command df "$SYSTEM_BIN/df" || true)}
SYSTEMCTL_BIN=${SYSTEMCTL_BIN:-$(resolve_command systemctl "$SYSTEM_BIN/systemctl" "$SYSTEM_SBIN/systemctl" || true)}
POSTQUEUE_BIN=${POSTQUEUE_BIN:-$(resolve_command postqueue "$SYSTEM_SBIN/postqueue" "$SYSTEM_BIN/postqueue" || true)}
OPENSSL_BIN=${OPENSSL_BIN:-$(resolve_command openssl "$SYSTEM_BIN/openssl" "$SYSTEM_SBIN/openssl" || true)}
NFT_BIN=${NFT_BIN:-$(resolve_command nft "$SYSTEM_SBIN/nft" "$SYSTEM_BIN/nft" || true)}

for pair in \
    "python3:$PYTHON3_BIN" \
    "postconf:$POSTCONF_BIN" \
    "ss:$SS_BIN" \
    "ip:$IP_BIN" \
    "getent:$GETENT_BIN" \
    "stat:$STAT_BIN" \
    "df:$DF_BIN" \
    "systemctl:$SYSTEMCTL_BIN"
do
    name=${pair%%:*}
    path=${pair#*:}
    [ -n "$path" ] && [ -x "$path" ] || fail "$name is unavailable"
done

[ -d "$REPO_ROOT/.git" ] || fail "repository is unavailable"
[ -f "$CONFIG" ] || fail "gateway configuration is unavailable"
[ -d "$ARCHIVE_ROOT" ] && [ ! -L "$ARCHIVE_ROOT" ] || fail "raw archive root is unavailable or unsafe"
[ -f "$STORE" ] && [ ! -L "$STORE" ] || fail "Mail Room store is unavailable or unsafe"

branch=$(git -C "$REPO_ROOT" branch --show-current)
[ "$branch" = "main" ] || fail "repository must be on main"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository working tree is not clean"

"$PYTHON3_BIN" - "$CONFIG" "$SERVICE_HOSTNAME" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
hostname = sys.argv[2]
data = json.loads(path.read_text(encoding="utf-8"))
if data.get("contract") != "wwcx.edge1-mail-gateway.v1":
    raise SystemExit("invalid Edge1 Mail Gateway contract")
if data.get("service_hostname") != hostname:
    raise SystemExit("service hostname does not match readiness target")
if data.get("activation") != {
    "public_smtp_listener_enabled": False,
    "production_mx_changes_authorized": False,
    "outbound_delivery_enabled": False,
}:
    raise SystemExit("gateway activation flags are not safely disabled")
ww = data.get("domains", {}).get("ww.cx", {})
if ww.get("mode") != "stay_external" or ww.get("catch_all_enabled") is not False:
    raise SystemExit("ww.cx is not preserved as external")
PY

"$SYSTEMCTL_BIN" is-active --quiet postfix || fail "Postfix is not active"

inet_interfaces=$("$POSTCONF_BIN" -h inet_interfaces)
virtual_transport=$("$POSTCONF_BIN" -h virtual_transport)
recipient_limit=$("$POSTCONF_BIN" -h wwcxmail_destination_recipient_limit)
virtual_domains=$("$POSTCONF_BIN" -h virtual_mailbox_domains)
virtual_maps=$("$POSTCONF_BIN" -h virtual_mailbox_maps)
message_limit=$("$POSTCONF_BIN" -h message_size_limit)
relay_domains=$("$POSTCONF_BIN" -h relay_domains)
recipient_restrictions=$("$POSTCONF_BIN" -h smtpd_recipient_restrictions)
master_line=$("$POSTCONF_BIN" -M wwcxmail/unix 2>/dev/null || true)

[ "$inet_interfaces" = "loopback-only" ] || fail "pre-activation Postfix must remain loopback-only"
[ "$virtual_transport" = "wwcxmail:" ] || fail "archive transport is not selected"
[ "$recipient_limit" = "1" ] || fail "one-recipient wwcxmail delivery is not active"
[ "$virtual_domains" = "hash:/etc/postfix/wwcx-edge1-managed-domains" ] || fail "managed-domain map is unexpected"
[ "$virtual_maps" = "regexp:/etc/postfix/wwcx-edge1-recipient-regexp" ] || fail "recipient map is unexpected"
[ "$message_limit" = "52428800" ] || fail "raw archive message-size boundary is unexpected"
[ -z "$relay_domains" ] || fail "relay_domains must remain empty"
printf '%s\n' "$recipient_restrictions" | grep -F 'reject_unauth_destination' >/dev/null || fail "relay denial is not explicit"
printf '%s\n' "$master_line" | grep -F 'edge1_mail_gateway_archive.py' >/dev/null || fail "wwcxmail is not archive-first"
printf '%s\n' "$master_line" | grep -F -- '--recipient ${original_recipient}' >/dev/null || fail "original recipient is not preserved"
printf '%s\n' "$master_line" | grep -F 'flags=ROq' >/dev/null || fail "X-Original-To preservation is not active"

listeners=$( ("$SS_BIN" -lntp 2>/dev/null || "$SS_BIN" -lnt) | awk '$4 ~ /(^|:|\])25$/ {print}' )
if [ -n "$listeners" ] && printf '%s\n' "$listeners" | grep -Ev '127\.0\.0\.1:25|\[::1\]:25|::1:25' | grep . >/dev/null 2>&1; then
    fail "TCP/25 is already exposed outside loopback"
fi

archive_stat=$("$STAT_BIN" -Lc '%U:%G %a %n' "$ARCHIVE_ROOT")
printf '%s\n' "$archive_stat" | grep -F 'wwcx-mail-gateway:wwcx-mail-gateway 700 ' >/dev/null || fail "archive root ownership or mode is unexpected"

default_if=$("$IP_BIN" -4 route show default | awk 'NR==1 {for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}')
[ -n "$default_if" ] || fail "default-route interface cannot be determined"
public_ipv4=$("$IP_BIN" -4 -o addr show dev "$default_if" scope global | awk 'NR==1 {split($4,a,"/"); print a[1]}')
[ -n "$public_ipv4" ] || fail "public IPv4 cannot be determined from the default-route interface"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
evidence=${EVIDENCE_ROOT:-/tmp/wwcx-edge1-mail-gateway-public-readiness-$stamp}
[ ! -e "$evidence" ] || fail "evidence path already exists"
install -d -o root -g root -m 0700 "$evidence"

{
    printf 'contract=wwcx.edge1-mail-gateway-public-readiness.v1\n'
    printf 'checked_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'repository_branch=%s\n' "$branch"
    printf 'repository_head=%s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
    printf 'service_hostname=%s\n' "$SERVICE_HOSTNAME"
    printf 'default_route_interface=%s\n' "$default_if"
    printf 'public_ipv4=%s\n' "$public_ipv4"
} > "$evidence/identity.txt"

git -C "$REPO_ROOT" status --short --branch > "$evidence/repository-status.txt"
"$IP_BIN" -brief address > "$evidence/network-addresses.txt"
"$IP_BIN" route show table all > "$evidence/network-routes.txt"
printf '%s\n' "$listeners" > "$evidence/port25-listeners.txt"
"$SS_BIN" -lntp > "$evidence/tcp-listeners.txt" 2>&1 || "$SS_BIN" -lnt > "$evidence/tcp-listeners.txt"

{
    for key in \
        myhostname \
        smtpd_banner \
        inet_interfaces \
        mynetworks \
        smtpd_recipient_restrictions \
        relay_domains \
        virtual_mailbox_domains \
        virtual_mailbox_maps \
        virtual_transport \
        wwcxmail_destination_recipient_limit \
        message_size_limit \
        smtpd_tls_security_level \
        smtpd_tls_cert_file \
        smtpd_tls_key_file
    do
        printf '%s = %s\n' "$key" "$("$POSTCONF_BIN" -h "$key" 2>/dev/null || true)"
    done
} > "$evidence/postfix-readiness.txt"
printf '%s\n' "$master_line" > "$evidence/wwcxmail-transport.txt"

"$STAT_BIN" -Lc '%U:%G %a %s %n' "$ARCHIVE_ROOT" "$STORE" > "$evidence/storage-stat.txt"
"$DF_BIN" -Pk "$ARCHIVE_ROOT" "$STORE" > "$evidence/storage-disk.txt"

if [ -n "$POSTQUEUE_BIN" ]; then
    "$POSTQUEUE_BIN" -p > "$evidence/postfix-queue.txt" 2>&1 || true
else
    printf 'postqueue unavailable\n' > "$evidence/postfix-queue.txt"
fi

if "$GETENT_BIN" ahostsv4 "$SERVICE_HOSTNAME" > "$evidence/dns-a.txt" 2>&1; then
    if awk -v ip="$public_ipv4" '$1 == ip {found=1} END {exit found ? 0 : 1}' "$evidence/dns-a.txt"; then
        dns_a_ready=yes
    else
        dns_a_ready=no
    fi
else
    dns_a_ready=no
fi

if "$GETENT_BIN" hosts "$public_ipv4" > "$evidence/dns-ptr.txt" 2>&1; then
    ptr_name=$(awk 'NR==1 {print $2}' "$evidence/dns-ptr.txt")
else
    ptr_name=
fi

ptr_present=no
fcrdns_ready=no
if [ -n "$ptr_name" ]; then
    ptr_present=yes
    if "$GETENT_BIN" ahostsv4 "$ptr_name" > "$evidence/dns-ptr-forward.txt" 2>&1 && \
       awk -v ip="$public_ipv4" '$1 == ip {found=1} END {exit found ? 0 : 1}' "$evidence/dns-ptr-forward.txt"; then
        fcrdns_ready=yes
    fi
else
    : > "$evidence/dns-ptr-forward.txt"
fi

cert=/etc/letsencrypt/live/$SERVICE_HOSTNAME/fullchain.pem
key=/etc/letsencrypt/live/$SERVICE_HOSTNAME/privkey.pem
tls_ready=no
{
    printf 'certificate=%s\n' "$cert"
    printf 'private_key=%s\n' "$key"
    if [ -f "$cert" ]; then
        "$STAT_BIN" -Lc 'certificate_stat=%U:%G %a %s %n' "$cert"
    else
        printf 'certificate_missing=true\n'
    fi
    if [ -f "$key" ]; then
        "$STAT_BIN" -Lc 'private_key_stat=%U:%G %a %s %n' "$key"
    else
        printf 'private_key_missing=true\n'
    fi
    if [ -f "$cert" ] && [ -f "$key" ] && [ -n "$OPENSSL_BIN" ]; then
        "$OPENSSL_BIN" x509 -in "$cert" -noout -subject -issuer -dates -ext subjectAltName 2>/dev/null || true
        if "$OPENSSL_BIN" x509 -in "$cert" -noout -ext subjectAltName 2>/dev/null | grep -F "DNS:$SERVICE_HOSTNAME" >/dev/null; then
            tls_ready=yes
        fi
    fi
} > "$evidence/tls-readiness.txt"

if [ -n "$NFT_BIN" ]; then
    "$NFT_BIN" list ruleset > "$evidence/firewall-ruleset.txt" 2>&1 || true
    grep -Ei 'tcp.*dport[[:space:]]+25|dport[[:space:]]+25.*tcp' "$evidence/firewall-ruleset.txt" > "$evidence/firewall-port25.txt" || true
else
    printf 'nft unavailable\n' > "$evidence/firewall-ruleset.txt"
    printf 'firewall inspection unavailable\n' > "$evidence/firewall-port25.txt"
fi

technical_prerequisites=yes
[ "$dns_a_ready" = yes ] || technical_prerequisites=no
[ "$ptr_present" = yes ] || technical_prerequisites=no
[ "$fcrdns_ready" = yes ] || technical_prerequisites=no
[ "$tls_ready" = yes ] || technical_prerequisites=no

{
    printf 'contract=wwcx.edge1-mail-gateway-public-readiness.v1\n'
    printf 'service_hostname=%s\n' "$SERVICE_HOSTNAME"
    printf 'public_ipv4=%s\n' "$public_ipv4"
    printf 'postfix_active=yes\n'
    printf 'tcp25_loopback_only=yes\n'
    printf 'archive_first_transport=yes\n'
    printf 'relay_denial_explicit=yes\n'
    printf 'archive_root_protected=yes\n'
    printf 'dns_a_points_to_edge1=%s\n' "$dns_a_ready"
    printf 'ptr_present=%s\n' "$ptr_present"
    printf 'ptr_forward_confirms=%s\n' "$fcrdns_ready"
    printf 'tls_mail_ww_cx_ready=%s\n' "$tls_ready"
    printf 'technical_prerequisites_complete=%s\n' "$technical_prerequisites"
    printf 'public_listener_activation_authorized=no\n'
    printf 'firewall_change_authorized=no\n'
    printf 'certificate_change_authorized=no\n'
    printf 'production_dns_mx_change_authorized=no\n'
    printf 'external_tcp25_probe=pending_until_public_listener_authorized\n'
    printf 'ww_cx_migration_authorized=no\n'
} > "$evidence/summary.txt"

cat > "$evidence/activation-gates.txt" <<'EOF'
Public activation remains a separate production gate.

Before public SMTP activation, independently authorize and validate:
- any required mail.ww.cx A/AAAA DNS change;
- any required reverse-DNS/PTR provider change;
- TLS certificate issuance/installation for mail.ww.cx if not already ready;
- the exact public Postfix bind/listener change;
- any firewall change required for inbound TCP/25;
- an external TCP/25 and SMTP relay-denial probe after exposure but before MX cutover;
- the first domain MX cutover (creekco.ca) as a separate action.

Do not migrate ww.cx in Edge1 Mail Gateway v1.
EOF

{
    cd "$evidence"
    find . -type f ! -name sha256.txt -print | LC_ALL=C sort | while IFS= read -r file; do
        sha256sum "$file"
    done
} > "$evidence/sha256.txt"

printf '%s\n' "$evidence"
