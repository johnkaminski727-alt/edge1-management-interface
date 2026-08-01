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
            echo "Read-only PJSIP ownership, include-order, HTTPS/TLS, and firewall-scope audit."
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

for command in asterisk awk grep sed sort ss systemctl find stat readlink date hostname id ip; do
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

print_config_directives() {
    file=$1
    [ -f "$file" ] || return 0
    awk '
        /^[[:space:]]*[#;]/{next}
        /^[[:space:]]*$/ {next}
        /^[[:space:]]*(#include|#tryinclude)[[:space:]]/ {
            print FILENAME ":" FNR ": " $0
        }
    ' "$file"
}

print_transport_sections() {
    file=$1
    [ -f "$file" ] || return 0
    awk '
        function flush() {
            if (section != "" && (is_transport || bind != "" || protocol != "")) {
                print FILENAME ":" section
                if (type_line != "") print "  " type_line
                if (protocol != "") print "  " protocol
                if (bind != "") print "  " bind
                if (external_media != "") print "  " external_media
                if (external_signaling != "") print "  " external_signaling
            }
        }
        /^[[:space:]]*\[[^]]+\][[:space:]]*$/ {
            flush()
            section=$0
            is_transport=0
            type_line=""
            protocol=""
            bind=""
            external_media=""
            external_signaling=""
            next
        }
        /^[[:space:]]*type[[:space:]]*=[[:space:]]*transport[[:space:]]*$/ {
            is_transport=1
            type_line=$0
            next
        }
        /^[[:space:]]*protocol[[:space:]]*=/ { protocol=$0; next }
        /^[[:space:]]*bind[[:space:]]*=/ { bind=$0; next }
        /^[[:space:]]*external_media_address[[:space:]]*=/ { external_media=$0; next }
        /^[[:space:]]*external_signaling_address[[:space:]]*=/ { external_signaling=$0; next }
        END { flush() }
    ' "$file"
}

print_http_settings() {
    file=$1
    [ -f "$file" ] || return 0
    awk '
        /^[[:space:]]*[#;]/ {next}
        /^[[:space:]]*(enabled|bindaddr|bindport|tlsenable|tlsbindaddr|tlsbindport|tlscertfile|tlsprivatekey)[[:space:]]*=/ {
            line=$0
            sub(/^[[:space:]]*/, "", line)
            print FILENAME ":" FNR ": " line
        }
    ' "$file"
}

echo "WW.CX ASTERISK TRANSPORT AND EXPOSURE AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no service, package, configuration, listener, route, certificate, or firewall changes"

section "CORE AND BOOT STATE"
asterisk -rx 'core show version'
asterisk -rx 'core show uptime'
asterisk -rx 'core show channels count'
echo "service_active=$(systemctl is-active asterisk 2>&1 || true)"
echo "service_enabled=$(systemctl is-enabled asterisk 2>&1 | tail -n 1 || true)"

section "CHANNEL DRIVERS AND PJSIP MODULES"
asterisk -rx 'core show channeltypes' 2>&1 | grep -E '(^Type|PJSIP|SIP|Local)' || true
asterisk -rx 'module show like chan_sip' 2>&1 || true
asterisk -rx 'module show like chan_pjsip' 2>&1 || true
asterisk -rx 'module show like res_pjsip' 2>&1 || true

section "PJSIP RUNTIME OBJECTS"
PJSIP_TRANSPORTS=$(asterisk -rx 'pjsip show transports' 2>&1 || true)
PJSIP_ENDPOINTS=$(asterisk -rx 'pjsip show endpoints' 2>&1 || true)
printf '%s\n' "$PJSIP_TRANSPORTS"
printf '%s\n' "$PJSIP_ENDPOINTS"

section "PJSIP INCLUDE ORDER"
INCLUDES_FOUND=0
for file in /etc/asterisk/pjsip.conf /etc/asterisk/pjsip_*.conf /etc/asterisk/pjsip.*.conf; do
    [ -f "$file" ] || continue
    output=$(print_config_directives "$file")
    if [ -n "$output" ]; then
        INCLUDES_FOUND=1
        printf '%s\n' "$output"
    fi
done
[ "$INCLUDES_FOUND" -eq 1 ] || warn "No explicit PJSIP include directives were found in the inspected files"

section "SANITIZED TRANSPORT DEFINITIONS"
TRANSPORT_OUTPUT=""
for file in /etc/asterisk/pjsip.conf /etc/asterisk/pjsip_*.conf /etc/asterisk/pjsip.*.conf; do
    [ -f "$file" ] || continue
    current=$(print_transport_sections "$file")
    if [ -n "$current" ]; then
        TRANSPORT_OUTPUT="${TRANSPORT_OUTPUT}${TRANSPORT_OUTPUT:+
}${current}"
    fi
done
printf '%s\n' "$TRANSPORT_OUTPUT"

DUPLICATE_SECTIONS=$(printf '%s\n' "$TRANSPORT_OUTPUT" |
    awk -F: '/:\[[^]]+\]$/ {name=$NF; count[name]++} END {for (name in count) if (count[name] > 1) print name " count=" count[name]}' |
    sort)
if [ -n "$DUPLICATE_SECTIONS" ]; then
    printf '%s\n' "$DUPLICATE_SECTIONS"
    warn "Duplicate PJSIP transport section names exist across configuration files"
fi

section "SIP LISTENER OWNERSHIP"
SIP_LISTENERS=$(ss -lntup 2>&1 | grep -E 'asterisk|kamailio|:5060|:5061' || true)
printf '%s\n' "$SIP_LISTENERS"
if printf '%s\n' "$SIP_LISTENERS" | grep -Eq '127\.0\.0\.1:5061[[:space:]].*asterisk'; then
    echo "PASS: Asterisk owns 127.0.0.1:5061"
else
    fail "Asterisk does not own expected loopback transport 127.0.0.1:5061"
fi
if printf '%s\n' "$PJSIP_TRANSPORTS" | grep -q 'No objects found'; then
    warn "PJSIP object registry exposes no transport despite an Asterisk-owned SIP listener"
fi

section "ASTERISK HTTP CONFIGURATION"
for file in /etc/asterisk/http.conf /etc/asterisk/http_custom.conf /etc/asterisk/http_additional.conf; do
    print_http_settings "$file"
done
asterisk -rx 'http show status' 2>&1 || true

section "HTTP AND HTTPS LISTENERS"
HTTP_LISTENERS=$(ss -lntp 2>&1 | grep -E 'asterisk|:8088|:8089' || true)
printf '%s\n' "$HTTP_LISTENERS"
if printf '%s\n' "$HTTP_LISTENERS" | grep -Eq '(^|[[:space:]])(\*|0\.0\.0\.0|\[::\]):8089[[:space:]]'; then
    warn "Asterisk HTTPS 8089 is wildcard-bound"
fi

section "HOST NETWORK ADDRESSES"
ip -brief address show 2>&1 | sed -E 's/[[:space:]]+/ /g'
if command -v wg >/dev/null 2>&1; then
    echo "WireGuard interfaces:"
    wg show interfaces 2>/dev/null || true
fi
if command -v sysctl >/dev/null 2>&1; then
    sysctl net.ipv6.bindv6only 2>/dev/null || true
fi

section "TLS CERTIFICATE METADATA"
CERT_PATH=$(awk '
    /^[[:space:]]*[#;]/ {next}
    /^[[:space:]]*tlscertfile[[:space:]]*=/ {
        line=$0
        sub(/^[^=]*=[[:space:]]*/, "", line)
        value=line
    }
    END {print value}
' /etc/asterisk/http.conf /etc/asterisk/http_custom.conf /etc/asterisk/http_additional.conf 2>/dev/null || true)
if [ -n "$CERT_PATH" ] && [ -f "$CERT_PATH" ]; then
    stat -c 'mode=%a owner=%U group=%G path=%n' "$CERT_PATH"
    if command -v openssl >/dev/null 2>&1; then
        openssl x509 -in "$CERT_PATH" -noout \
            -subject -issuer -serial -dates -fingerprint -sha256 2>&1 || true
        openssl x509 -in "$CERT_PATH" -noout -ext subjectAltName 2>&1 || true
    fi
else
    warn "TLS certificate path was not resolved from Asterisk HTTP configuration"
fi

section "LOCAL TLS HANDSHAKE"
if command -v openssl >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    TLS_OUTPUT=$(timeout 10 openssl s_client -connect 127.0.0.1:8089 -servername "$HOST" -brief </dev/null 2>&1 || true)
    printf '%s\n' "$TLS_OUTPUT"
    if printf '%s\n' "$TLS_OUTPUT" | grep -Eq 'Protocol version:|CONNECTION ESTABLISHED'; then
        echo "PASS: local TLS handshake completed"
    else
        warn "Local TLS handshake was not confirmed"
    fi
else
    warn "openssl or timeout is unavailable"
fi

section "REVERSE PROXY AND CONSUMER REFERENCES"
REFERENCE_ROOTS="/etc/apache2 /etc/nginx /etc/caddy /opt/edge1-management-interface /opt/bigbird-ai-gateway"
REFERENCE_FOUND=0
for root in $REFERENCE_ROOTS; do
    [ -d "$root" ] || continue
    matches=$(grep -RIl --exclude='*.key' --exclude='*.pem' --exclude='*.crt' --exclude='*.p12' --exclude='*.pfx' --exclude='*.sqlite*' --exclude='*.db' --exclude='*.log' -- '8089\|wss://\|/ws' "$root" 2>/dev/null | sort -u || true)
    if [ -n "$matches" ]; then
        REFERENCE_FOUND=1
        printf '%s\n' "$matches"
    fi
done
[ "$REFERENCE_FOUND" -eq 1 ] || echo "No configuration or repository file references to 8089, wss://, or /ws were found in the inspected roots."

section "FIREWALL POLICY SUMMARY"
if command -v nft >/dev/null 2>&1; then
    NFT_RULESET=$(nft -a list ruleset 2>/dev/null || true)
    printf '%s\n' "$NFT_RULESET" |
        awk '
            /^[[:space:]]*table / {table=$0; print table; next}
            /^[[:space:]]*chain / {chain=$0; print chain; next}
            /hook input/ || /policy (accept|drop|reject)/ {print}
        '
    NFT_PORTS=$(printf '%s\n' "$NFT_RULESET" | grep -E '(^|[^0-9])(5060|5061|8088|8089)([^0-9]|$)' || true)
    if [ -n "$NFT_PORTS" ]; then
        echo "Relevant nftables rules:"
        printf '%s\n' "$NFT_PORTS"
    else
        echo "No explicit nftables rule references to 5060, 5061, 8088, or 8089 were found."
    fi
elif command -v iptables-save >/dev/null 2>&1; then
    iptables-save 2>/dev/null |
        grep -E '^:(INPUT|FORWARD|OUTPUT)|(^|[^0-9])(5060|5061|8088|8089)([^0-9]|$)' || true
else
    warn "No supported firewall inspection command was available"
fi

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi

echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No configuration, listener, certificate, firewall, route, service, or package change was performed."
