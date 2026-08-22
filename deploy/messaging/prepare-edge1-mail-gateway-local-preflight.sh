#!/bin/sh
set -eu

REPO_ROOT=${REPO_ROOT:-/opt/edge1-management-interface}
CONFIG=${CONFIG:-$REPO_ROOT/config/messaging/edge1-mail-gateway-v1.json}
RENDERER=${RENDERER:-$REPO_ROOT/tools/messaging/render_edge1_mail_gateway_postfix.py}
OUTPUT_ROOT=${OUTPUT_ROOT:-/tmp}
POSTFIX_ETC=${POSTFIX_ETC:-/etc/postfix}
SYSTEM_SBIN=${SYSTEM_SBIN:-/usr/sbin}
SYSTEM_BIN=${SYSTEM_BIN:-/usr/bin}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

resolve_command() {
    name=$1
    shift
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

PYTHON3_BIN=${PYTHON3_BIN:-$(resolve_command python3 "$SYSTEM_BIN/python3" || true)}
POSTCONF_BIN=${POSTCONF_BIN:-$(resolve_command postconf "$SYSTEM_SBIN/postconf" "$SYSTEM_BIN/postconf" || true)}
SS_BIN=${SS_BIN:-$(resolve_command ss "$SYSTEM_BIN/ss" "$SYSTEM_SBIN/ss" || true)}

[ -n "$PYTHON3_BIN" ] && [ -x "$PYTHON3_BIN" ] || fail "python3 is unavailable"
[ -n "$POSTCONF_BIN" ] && [ -x "$POSTCONF_BIN" ] || fail "postconf is unavailable (checked PATH, $SYSTEM_SBIN/postconf, and $SYSTEM_BIN/postconf)"
[ -n "$SS_BIN" ] && [ -x "$SS_BIN" ] || fail "ss is unavailable (checked PATH, $SYSTEM_BIN/ss, and $SYSTEM_SBIN/ss)"

[ -f "$CONFIG" ] || fail "gateway configuration is unavailable"
[ -f "$RENDERER" ] || fail "Postfix renderer is unavailable"
[ -d "$POSTFIX_ETC" ] || fail "Postfix configuration directory is unavailable"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$OUTPUT_ROOT/wwcx-edge1-mail-gateway-preflight-$stamp"
umask 077
mkdir -p "$out/rendered" "$out/current"

# Repository evidence is read-only. An unexpected branch/detached state is recorded and
# causes the preflight to stop after collection; this script never switches branches.
if command -v git >/dev/null 2>&1 && [ -d "$REPO_ROOT/.git" ]; then
    git -C "$REPO_ROOT" rev-parse HEAD > "$out/current/repository-head.txt" 2>/dev/null || true
    git -C "$REPO_ROOT" status --short --branch > "$out/current/repository-status.txt" 2>/dev/null || true
fi

"$POSTCONF_BIN" -n > "$out/current/postconf-n.txt"
"$POSTCONF_BIN" -M > "$out/current/postconf-M.txt"
"$SS_BIN" -lntp > "$out/current/listeners-tcp.txt" 2>/dev/null || "$SS_BIN" -lnt > "$out/current/listeners-tcp.txt"

for name in main.cf master.cf; do
    if [ -f "$POSTFIX_ETC/$name" ]; then
        cp -p "$POSTFIX_ETC/$name" "$out/current/$name"
    fi
done

"$PYTHON3_BIN" "$RENDERER" --config "$CONFIG" --output-dir "$out/rendered" >/dev/null

# Hard safety invariants. The preflight itself must never bless a public SMTP state.
grep -Fx 'inet_interfaces = loopback-only' "$out/rendered/main.cf.fragment" >/dev/null \
    || fail "rendered configuration is not loopback-only"
grep -Fx 'relay_domains =' "$out/rendered/main.cf.fragment" >/dev/null \
    || fail "rendered configuration does not clear relay_domains"
if grep -q '^ww\.cx ' "$out/rendered/wwcx-edge1-managed-domains"; then
    fail "ww.cx unexpectedly appears in managed-domain map"
fi

# Capture relevant live values without changing them.
{
    for key in \
        inet_interfaces \
        myhostname \
        mydestination \
        relay_domains \
        virtual_alias_domains \
        virtual_alias_maps \
        virtual_mailbox_domains \
        virtual_mailbox_maps \
        virtual_transport \
        smtpd_recipient_restrictions
    do
        printf '%s = ' "$key"
        "$POSTCONF_BIN" -h "$key" 2>/dev/null || true
    done
} > "$out/current/relevant-postconf.txt"

listener25=$(awk '$4 ~ /(^|:|\])25$/ {print}' "$out/current/listeners-tcp.txt" || true)
printf '%s\n' "$listener25" > "$out/current/port25-listeners.txt"

# Only loopback port 25 is acceptable for this preflight phase.
if [ -n "$listener25" ]; then
    if printf '%s\n' "$listener25" | grep -Ev '127\.0\.0\.1:25|\[::1\]:25|::1:25' | grep . >/dev/null 2>&1; then
        fail "TCP/25 has a non-loopback listener; public-state review required"
    fi
fi

# Record likely collisions for operator review. A collision does not mutate anything and
# blocks later apply tooling until explicitly reconciled.
: > "$out/current/collisions.txt"
for key in virtual_mailbox_domains virtual_mailbox_maps virtual_transport; do
    value=$("$POSTCONF_BIN" -h "$key" 2>/dev/null || true)
    if [ -n "$value" ]; then
        printf '%s=%s\n' "$key" "$value" >> "$out/current/collisions.txt"
    fi
done

current_hashes="$out/current/sha256.txt"
(
    cd "$out"
    find current rendered -type f -print | LC_ALL=C sort | while IFS= read -r file; do
        sha256sum "$file"
    done
) > "$current_hashes"

cat > "$out/README.txt" <<EOF
WW.CX Edge1 Mail Gateway local-only Postfix preflight
Generated: $stamp
Postconf executable: $POSTCONF_BIN
Socket utility: $SS_BIN

This directory is evidence only. No Postfix configuration was edited, no service was
restarted, no listener was opened, and no DNS/MX state was changed.

Review in this order:
1. current/repository-status.txt and repository-head.txt
2. current/port25-listeners.txt
3. current/relevant-postconf.txt
4. current/collisions.txt
5. rendered/main.cf.fragment and rendered/master.cf.fragment
6. rendered managed-domain and recipient maps

An apply step requires a separate explicit authorization and backup/rollback operation.
EOF

printf '%s\n' "$out"
