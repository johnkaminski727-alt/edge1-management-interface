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
            echo "Read-only follow-up for PJSIP transport visibility, boot persistence, and TCP 8089 exposure."
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

for command in asterisk ss systemctl grep awk sed find readlink date hostname id; do
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

echo "WW.CX ASTERISK WARNING FOLLOW-UP AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no package, service, configuration, listener, route, or firewall changes"

section "CORE"
asterisk -rx 'core show version'
asterisk -rx 'core show uptime'
asterisk -rx 'core show channels count'

section "PJSIP CLI TRANSPORTS"
PJSIP_TRANSPORTS=$(asterisk -rx 'pjsip show transports' 2>&1 || true)
printf '%s\n' "$PJSIP_TRANSPORTS"

section "PJSIP CLI ENDPOINTS"
asterisk -rx 'pjsip show endpoints' 2>&1 || true

section "ASTERISK UDP LISTENERS"
UDP_LISTENERS=$(ss -lunp 2>&1 | grep -E 'asterisk|:5061' || true)
printf '%s\n' "$UDP_LISTENERS"

if printf '%s\n' "$UDP_LISTENERS" | grep -Eq '127\.0\.0\.1:5061[[:space:]]'; then
    echo "PASS: Asterisk owns loopback UDP 127.0.0.1:5061"
else
    fail "Asterisk loopback UDP listener 127.0.0.1:5061 was not observed"
fi

if printf '%s\n' "$PJSIP_TRANSPORTS" | grep -q 'No objects found'; then
    if printf '%s\n' "$UDP_LISTENERS" | grep -Eq '127\.0\.0\.1:5061[[:space:]]'; then
        warn "PJSIP CLI reports no transport objects although the Asterisk process owns 127.0.0.1:5061"
    else
        fail "PJSIP CLI reports no transport objects and no expected listener is present"
    fi
fi

section "SANITIZED PJSIP TRANSPORT CONFIGURATION"
CONFIG_FOUND=0
for file in /etc/asterisk/pjsip*.conf; do
    [ -f "$file" ] || continue
    CONFIG_FOUND=1
    awk '
        function flush() {
            if (is_transport) {
                print FILENAME ":" section
                if (protocol != "") print "  " protocol
                if (bind != "") print "  " bind
            }
        }
        /^\[[^]]+\][[:space:]]*$/ {
            flush()
            section=$0
            is_transport=0
            protocol=""
            bind=""
            next
        }
        /^[[:space:]]*type[[:space:]]*=[[:space:]]*transport[[:space:]]*$/ {
            is_transport=1
            next
        }
        /^[[:space:]]*protocol[[:space:]]*=/ {
            protocol=$0
            next
        }
        /^[[:space:]]*bind[[:space:]]*=/ {
            bind=$0
            next
        }
        END { flush() }
    ' "$file"
done
[ "$CONFIG_FOUND" -eq 1 ] || warn "No /etc/asterisk/pjsip*.conf files were found"

section "SERVICE AND BOOT PERSISTENCE"
ACTIVE=$(systemctl is-active asterisk 2>&1 || true)
ENABLED=$(systemctl is-enabled asterisk 2>/dev/null || true)
echo "systemctl active: $ACTIVE"
echo "systemctl enabled: $ENABLED"
systemctl status asterisk --no-pager --full 2>&1 | sed -n '1,35p' || true

echo
echo "SysV startup links:"
RC_LINKS=$(find /etc/rc0.d /etc/rc1.d /etc/rc2.d /etc/rc3.d /etc/rc4.d /etc/rc5.d /etc/rc6.d \
    -maxdepth 1 -type l -name '*asterisk*' -print 2>/dev/null || true)
if [ -n "$RC_LINKS" ]; then
    printf '%s\n' "$RC_LINKS"
    for link in $RC_LINKS; do
        printf '%s -> %s\n' "$link" "$(readlink "$link" 2>/dev/null || true)"
    done
else
    warn "No SysV Asterisk startup links were observed"
fi

if [ "$ACTIVE" != "active" ]; then
    fail "Asterisk service wrapper is not active"
fi
if [ "$ENABLED" != "enabled" ]; then
    warn "systemd does not confirm Asterisk boot enablement; evaluate SysV links before changing startup policy"
fi

section "ASTERISK HTTP/TLS STATUS"
HTTP_STATUS=$(asterisk -rx 'http show status' 2>&1 || true)
printf '%s\n' "$HTTP_STATUS"

section "RELEVANT TCP LISTENERS"
TCP_LISTENERS=$(ss -lntp 2>&1 | grep -E 'asterisk|:5038|:8088|:8089' || true)
printf '%s\n' "$TCP_LISTENERS"

if printf '%s\n' "$TCP_LISTENERS" | grep -Eq '(^|[[:space:]])(\*|0\.0\.0\.0|\[::\]):8089[[:space:]]'; then
    warn "Asterisk TCP 8089 is bound beyond loopback"
fi

if command -v openssl >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    section "LOCAL TLS HANDSHAKE TO 8089"
    TLS_OUTPUT=$(timeout 10 openssl s_client -connect 127.0.0.1:8089 -servername "$HOST" -brief </dev/null 2>&1 || true)
    printf '%s\n' "$TLS_OUTPUT"
    if printf '%s\n' "$TLS_OUTPUT" | grep -Eq 'Protocol version:|CONNECTION ESTABLISHED'; then
        echo "PASS: local TLS handshake completed on 8089"
    else
        warn "local TLS handshake on 8089 was not confirmed"
    fi
else
    warn "openssl or timeout is unavailable; TLS handshake was not tested"
fi

if command -v nft >/dev/null 2>&1; then
    section "FILTER RULE REFERENCES"
    NFT_MATCHES=$(nft list ruleset 2>/dev/null | grep -E '(^|[^0-9])(5038|5061|8088|8089)([^0-9]|$)' || true)
    if [ -n "$NFT_MATCHES" ]; then
        printf '%s\n' "$NFT_MATCHES"
    else
        echo "No explicit references to 5038, 5061, 8088, or 8089 were found in the rendered nftables ruleset."
    fi
fi

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Follow-up state: FAILED"
    exit 1
fi

echo "Follow-up state: READ-ONLY REVIEW COMPLETE"
echo "Warnings require review but do not by themselves authorize a configuration, firewall, listener, or service-startup change."
