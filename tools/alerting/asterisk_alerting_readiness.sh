#!/bin/sh
set -eu

EXPECTED_HOST=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-host)
            [ "$#" -ge 2 ] || { echo "ERROR missing hostname" >&2; exit 2; }
            EXPECTED_HOST=$2
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--expected-host edge1.ww.cx]"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

for command in hostname asterisk pgrep ss systemctl grep date id; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

HOST=$(hostname -f)
if [ -n "$EXPECTED_HOST" ] && [ "$HOST" != "$EXPECTED_HOST" ]; then
    echo "ERROR expected host $EXPECTED_HOST, found $HOST" >&2
    exit 2
fi

[ "$(id -u)" -eq 0 ] || {
    echo "ERROR run with sudo so Asterisk CLI and listener ownership are complete" >&2
    exit 2
}

failure_count=0
warning_count=0

warn() {
    warning_count=$((warning_count + 1))
    echo "WARNING: $1"
}

fail() {
    failure_count=$((failure_count + 1))
    echo "FAIL: $1"
}

capture() {
    label=$1
    shift
    echo
    echo "=== $label ==="
    "$@"
}

module_running() {
    module=$1
    output=$(asterisk -rx "module show like $module" 2>&1 || true)
    printf '%s\n' "$output"
    if ! printf '%s\n' "$output" |
        grep -Eq "^${module}(\.so)?[[:space:]].*[[:space:]]Running[[:space:]]"; then
        fail "Asterisk module ${module}.so is not running"
    fi
}

echo "WW.CX ASTERISK ALERTING READINESS AUDIT"
echo "Host: $HOST"
echo "Time: $(date -Is)"
echo "Mode: read-only; no configuration or calls are changed"

echo
echo "=== PROCESS ==="
PROCESS_OUTPUT=$(pgrep -a asterisk 2>&1 || true)
printf '%s\n' "$PROCESS_OUTPUT"
[ -n "$PROCESS_OUTPUT" ] || fail "Asterisk process was not found"

capture "CORE VERSION" asterisk -rx "core show version"
capture "CORE UPTIME" asterisk -rx "core show uptime"
CHANNELS=$(asterisk -rx 'core show channels count' 2>&1 || true)
echo
echo "=== CHANNELS ==="
printf '%s\n' "$CHANNELS"

for module in app_playtones app_senddtmf dsp chan_pjsip res_pjsip res_pjsip_sdp_rtp; do
    echo
    echo "=== MODULE $module ==="
    module_running "$module"
done

TRANSPORTS=$(asterisk -rx 'pjsip show transports' 2>&1 || true)
ENDPOINTS=$(asterisk -rx 'pjsip show endpoints' 2>&1 || true)
echo
echo "=== PJSIP TRANSPORTS ==="
printf '%s\n' "$TRANSPORTS"
echo
echo "=== PJSIP ENDPOINTS ==="
printf '%s\n' "$ENDPOINTS"

printf '%s\n' "$TRANSPORTS" | grep -q "127.0.0.1:5061" || \
    warn "expected loopback Asterisk transport 127.0.0.1:5061 was not observed"
if printf '%s\n' "$ENDPOINTS" | grep -Eq "Objects found:[[:space:]]+[1-9]"; then
    warn "PJSIP endpoints exist; any later alert adapter requires explicit endpoint allowlisting"
fi

ENABLED=$(systemctl is-enabled asterisk 2>&1 || true)
ACTIVE=$(systemctl is-active asterisk 2>&1 || true)
echo
echo "=== SERVICE WRAPPER ==="
echo "active: $ACTIVE"
echo "enabled: $ENABLED"
[ "$ACTIVE" = "active" ] || warn "systemd wrapper does not report active"
[ "$ENABLED" = "enabled" ] || warn "Asterisk boot enablement is not confirmed by systemd"

LISTENERS=$(ss -lntup 2>&1 | grep -E 'asterisk|kamailio|:5060|:5061|:5038|:8088|:8089' || true)
echo
echo "=== RELEVANT LISTENERS ==="
printf '%s\n' "$LISTENERS"
if printf '%s\n' "$LISTENERS" |
    grep -Eq 'LISTEN.*(\*|0\.0\.0\.0|\[::\]):8089'; then
    warn "Asterisk TCP 8089 appears non-loopback; verify TLS, authentication, and firewall policy"
fi

DIALPLAN=$(asterisk -rx 'dialplan show' 2>&1 |
    grep -Ei 'CAP-CP|EBS|wwcx-alerting|alerting-lab' || true)
echo
echo "=== EXISTING ALERTING DIALPLAN MATCHES ==="
if [ -n "$DIALPLAN" ]; then
    printf '%s\n' "$DIALPLAN"
    warn "an alerting-related dialplan match exists and must be reviewed before integration"
else
    echo "none"
fi

echo
echo "=== RESULT ==="
echo "Warnings: $warning_count"
echo "Failures: $failure_count"
if [ "$failure_count" -gt 0 ]; then
    echo "Readiness: NOT READY"
    exit 1
fi

echo "Readiness: BASE CAPABILITIES PRESENT"
echo "This result does not authorize Actual alerts, CAP feed connectivity, call origination, or public distribution."
