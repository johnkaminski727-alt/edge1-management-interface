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
            echo "Read-only sanitized PJSIP startup and runtime-cause audit."
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

for command in asterisk awk grep sed sort ss systemctl find stat date hostname id ps tail sha256sum; do
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

sanitize_stream() {
    sed -E \
        -e 's#([sS][iI][pP][sS]?:)[^[:space:]>;,]+#\1[redacted]#g' \
        -e 's#PJSIP/[^[:space:]]+#PJSIP/[redacted]#g' \
        -e 's#[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}#[email]#g' \
        -e 's#([0-9]{1,3}\.){3}[0-9]{1,3}#[ip]#g' \
        -e 's#(^|[^0-9])[0-9]{7,}([^0-9]|$)#\1[number]\2#g' \
        -e 's#[A-Fa-f0-9]{32,}#[token]#g'
}

transport_sections() {
    file=$1
    [ -f "$file" ] || return 0
    awk '
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
    ' "$file"
}

echo "WW.CX ASTERISK PJSIP RUNTIME CAUSE AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; sanitized diagnostics only; no configuration, service, listener, route, certificate, firewall, package, call, or logger change"

section "CORE STATE"
asterisk -rx 'core show version'
asterisk -rx 'core show uptime'
asterisk -rx 'core show channels count'
echo "service_active=$(systemctl is-active asterisk 2>&1 || true)"
echo "service_enabled=$(systemctl is-enabled asterisk 2>&1 | tail -n 1 || true)"

PID=$(ps -C asterisk -o pid= 2>/dev/null | awk 'NR==1 {print $1}')
if [ -z "$PID" ]; then
    fail "Asterisk process PID was not found"
else
    echo "asterisk_pid=$PID"
    ps -p "$PID" -o pid=,lstart=,etime=,cmd= 2>/dev/null | sanitize_stream
fi

section "TRANSPORT INCLUDE AND DEFINITION ORDER"
awk '
    /^[[:space:]]*#(include|tryinclude)[[:space:]]+/ {
        print FILENAME ":" FNR ":" $0
    }
' /etc/asterisk/pjsip.conf /etc/asterisk/pjsip.transports.conf 2>/dev/null || true

TRANSPORT_OUTPUT=""
for file in /etc/asterisk/pjsip.transports_custom.conf /etc/asterisk/pjsip.transports.conf /etc/asterisk/pjsip.transports_custom_post.conf; do
    [ -f "$file" ] || continue
    current=$(transport_sections "$file")
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
    warn "Duplicate transport category names are present"
fi

section "PJSIP RUNTIME REGISTRY"
TRANSPORTS=$(asterisk -rx 'pjsip show transports' 2>&1 || true)
printf '%s\n' "$TRANSPORTS"
asterisk -rx 'pjsip show transport 0.0.0.0-udp' 2>&1 || true
asterisk -rx 'module show like chan_pjsip' 2>&1 || true
asterisk -rx 'module show like res_pjsip' 2>&1 || true

if printf '%s\n' "$TRANSPORTS" | grep -q 'No objects found'; then
    warn "PJSIP runtime registry exposes no transport"
fi

section "LISTENER OWNERSHIP"
LISTENERS=$(ss -lntup 2>&1 | grep -E 'asterisk|kamailio|:5060|:5061' || true)
printf '%s\n' "$LISTENERS"
if printf '%s\n' "$LISTENERS" | grep -Eq '127\.0\.0\.1:5061[[:space:]].*asterisk'; then
    echo "PASS: Asterisk owns loopback UDP 127.0.0.1:5061"
else
    fail "Asterisk does not own expected loopback UDP 127.0.0.1:5061"
fi

section "SANITIZED SYSTEM JOURNAL DIAGNOSTICS"
if command -v journalctl >/dev/null 2>&1; then
    JOURNAL_MATCHES=$(journalctl -u asterisk --no-pager -o short-iso --since '2026-07-31 23:30:00 UTC' 2>/dev/null |
        grep -Ei 'pjsip|transport|sorcery|bind|address already in use|unable to|failed to|error|warning' |
        tail -n 250 |
        sanitize_stream || true)
    if [ -n "$JOURNAL_MATCHES" ]; then
        printf '%s\n' "$JOURNAL_MATCHES"
    else
        echo "No matching Asterisk unit journal diagnostics were found in the inspected window."
    fi
else
    echo "journalctl is unavailable"
fi

section "SANITIZED ASTERISK LOG DIAGNOSTICS"
ASTERISK_LOG_FOUND=0
for logfile in /var/log/asterisk/full /var/log/asterisk/messages; do
    [ -f "$logfile" ] || continue
    ASTERISK_LOG_FOUND=1
    echo "source=$logfile"
    LOG_MATCHES=$(tail -n 30000 "$logfile" 2>/dev/null |
        grep -Ei 'res_pjsip|chan_pjsip|pjsip.*transport|transport.*pjsip|sorcery|address already in use|unable to bind|failed to bind|could not create.*transport|unable to create.*transport|duplicate.*transport|error.*transport|warning.*transport' |
        tail -n 300 |
        sanitize_stream || true)
    if [ -n "$LOG_MATCHES" ]; then
        printf '%s\n' "$LOG_MATCHES"
    else
        echo "No matching sanitized PJSIP transport diagnostics were found in the current log tail."
    fi
done
[ "$ASTERISK_LOG_FOUND" -eq 1 ] || echo "No standard Asterisk text log was present."

section "CONFIGURATION HASHES"
for file in /etc/asterisk/pjsip.conf /etc/asterisk/pjsip.transports.conf /etc/asterisk/pjsip.transports_custom.conf /etc/asterisk/pjsip.transports_custom_post.conf; do
    [ -f "$file" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file"
    sha256sum "$file"
done

section "RESULT"
echo "Warnings: $warnings"
echo "Failures: $failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi

echo "Audit state: READ-ONLY REVIEW COMPLETE"
echo "No configuration, service, listener, route, certificate, firewall, package, call, or logger change was performed."
