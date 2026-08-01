#!/bin/sh
set -eu
umask 077

EXPECTED_HOST="edge1.ww.cx"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-host)
            [ "$#" -ge 2 ] || { echo "ERROR missing hostname" >&2; exit 2; }
            EXPECTED_HOST=$2
            shift 2
            ;;
        -h|--help)
            echo "Usage: sudo $0 [--expected-host HOST]"
            echo "Read-only follow-up for PJSIP include order, runtime ownership, consumer references, and firewall policy."
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run with sudo" >&2; exit 2; }
HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || {
    echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2
    exit 2
}

for command in asterisk grep awk sort ss systemctl stat sha256sum date hostname id; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

warnings=0
failures=0

warn() {
    warnings=$((warnings + 1))
    echo "WARNING: $*"
}

fail() {
    failures=$((failures + 1))
    echo "FAIL: $*"
}

section() {
    echo
    echo "=== $* ==="
}

echo "WW.CX ASTERISK TRANSPORT POLICY FOLLOW-UP AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no configuration, service, listener, route, certificate, firewall, package, or call change"

section "CORE STATE"
asterisk -rx 'core show version'
asterisk -rx 'core show uptime'
asterisk -rx 'core show channels count'
echo "service_active=$(systemctl is-active asterisk 2>&1 || true)"
echo "service_enabled=$(systemctl is-enabled asterisk 2>&1 | tail -n 1 || true)"

section "PJSIP INCLUDE ORDER"
INCLUDE_OUTPUT=""
for file in /etc/asterisk/pjsip.conf /etc/asterisk/pjsip_*.conf /etc/asterisk/pjsip.*.conf; do
    [ -f "$file" ] || continue
    current=$(grep -HnE '^[[:space:]]*#(try)?include[[:space:]]+' "$file" 2>/dev/null || true)
    if [ -n "$current" ]; then
        INCLUDE_OUTPUT="${INCLUDE_OUTPUT}${INCLUDE_OUTPUT:+
}${current}"
    fi
done
if [ -n "$INCLUDE_OUTPUT" ]; then
    printf '%s\n' "$INCLUDE_OUTPUT"
else
    warn "No PJSIP include directives were found"
fi

section "PJSIP FILE METADATA"
for file in /etc/asterisk/pjsip.conf /etc/asterisk/pjsip_*.conf /etc/asterisk/pjsip.*.conf; do
    [ -f "$file" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file"
    sha256sum "$file"
done

section "SANITIZED TRANSPORT DEFINITIONS"
TRANSPORT_OUTPUT=""
for file in /etc/asterisk/pjsip.conf /etc/asterisk/pjsip_*.conf /etc/asterisk/pjsip.*.conf; do
    [ -f "$file" ] || continue
    current=$(awk '
        function flush() {
            if (section != "" && is_transport) {
                print FILENAME ":" section
                if (protocol != "") print "  " protocol
                if (bind != "") print "  " bind
            }
        }
        /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
            flush()
            section=$0
            is_transport=0
            protocol=""
            bind=""
            next
        }
        /^[[:space:]]*type[[:space:]]*=[[:space:]]*transport[[:space:]]*$/ {is_transport=1; next}
        /^[[:space:]]*protocol[[:space:]]*=/ {protocol=$0; next}
        /^[[:space:]]*bind[[:space:]]*=/ {bind=$0; next}
        END {flush()}
    ' "$file")
    if [ -n "$current" ]; then
        TRANSPORT_OUTPUT="${TRANSPORT_OUTPUT}${TRANSPORT_OUTPUT:+
}${current}"
    fi
done
printf '%s\n' "$TRANSPORT_OUTPUT"
DUPLICATES=$(printf '%s\n' "$TRANSPORT_OUTPUT" |
    awk -F: '/:\[[^]]+\]$/ {name=$NF; count[name]++} END {for (name in count) if (count[name] > 1) print name " count=" count[name]}' |
    sort)
if [ -n "$DUPLICATES" ]; then
    printf '%s\n' "$DUPLICATES"
    warn "Duplicate transport section names remain present"
fi

section "PJSIP RUNTIME"
TRANSPORTS=$(asterisk -rx 'pjsip show transports' 2>&1 || true)
printf '%s\n' "$TRANSPORTS"
asterisk -rx 'pjsip show transport 0.0.0.0-udp' 2>&1 || true
asterisk -rx 'pjsip show settings' 2>&1 || true
if printf '%s\n' "$TRANSPORTS" | grep -q 'No objects found'; then
    warn "PJSIP runtime registry still exposes no transport"
fi

section "SORCERY AND REALTIME MAPPINGS"
MAPPINGS=$(grep -HnE '^[[:space:]]*(res_pjsip|ps_[A-Za-z0-9_]+)[[:space:]]*=' \
    /etc/asterisk/sorcery.conf /etc/asterisk/extconfig.conf 2>/dev/null || true)
if [ -n "$MAPPINGS" ]; then
    printf '%s\n' "$MAPPINGS"
else
    echo "No matching PJSIP sorcery or realtime mappings were found."
fi

section "LISTENER OWNERSHIP"
LISTENERS=$(ss -lntup 2>&1 | grep -E 'asterisk|kamailio|:5060|:5061|:8088|:8089' || true)
printf '%s\n' "$LISTENERS"
if printf '%s\n' "$LISTENERS" | grep -Eq '127\.0\.0\.1:5061[[:space:]].*asterisk'; then
    echo "PASS: Asterisk owns loopback UDP 127.0.0.1:5061"
else
    fail "Expected Asterisk loopback listener 127.0.0.1:5061 was not observed"
fi
if printf '%s\n' "$LISTENERS" | grep -Eq '(^|[[:space:]])(\*|0\.0\.0\.0|\[::\]):8089[[:space:]]'; then
    warn "Asterisk HTTPS 8089 remains wildcard-bound"
fi

section "FOCUSED CONSUMER REFERENCES"
REFERENCE_FOUND=0
for root in /etc/apache2 /etc/nginx /etc/caddy /opt/edge1-management-interface /opt/bigbird-ai-gateway; do
    [ -d "$root" ] || continue
    matches=$(grep -RIl \
        --exclude-dir=.git \
        --exclude-dir='venv*' \
        --exclude-dir='.venv*' \
        --exclude-dir=__pycache__ \
        --exclude='*.key' --exclude='*.pem' --exclude='*.crt' \
        --exclude='*.sqlite*' --exclude='*.db' --exclude='*.log' \
        -- '8089\|wss://\|/ws' "$root" 2>/dev/null | sort -u || true)
    if [ -n "$matches" ]; then
        REFERENCE_FOUND=1
        printf '%s\n' "$matches"
    fi
done
[ "$REFERENCE_FOUND" -eq 1 ] || echo "No focused reverse-proxy or application consumer references were found."

section "FIREWALL INPUT POLICY PATHS"
if command -v nft >/dev/null 2>&1; then
    for spec in \
        'inet wwcxfw input' \
        'ip filter INPUT' \
        'ip filter fail2ban-PBX-GUI' \
        'ip filter fail2ban-SIP'; do
        set -- $spec
        family=$1
        table=$2
        chain=$3
        echo
        echo "--- nft $family $table $chain ---"
        nft -a list chain "$family" "$table" "$chain" 2>&1 || true
    done
else
    warn "nft is unavailable"
fi

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi

echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No configuration, service, listener, route, certificate, firewall, package, or call change was performed."
